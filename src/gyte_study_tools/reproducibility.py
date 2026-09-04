"""Verification helpers for publication reproducibility semantics."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class ReproducibilityError(RuntimeError):
    """Raised when publication reproducibility cannot be verified safely."""


@dataclass(frozen=True)
class ArtifactIdentity:
    format: str
    level: str
    byte_sha256: str
    normalized_sha256: str


@dataclass(frozen=True)
class ReproducibilityReport:
    manifest_path: Path
    reviewed_source_sha256: str
    artifacts: dict[str, ArtifactIdentity]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script", "head"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "head"} and self.hidden_depth > 0:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0 and data.strip():
            self.parts.append(data)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    """Normalize human-visible text for content-equivalence comparison."""
    value = unicodedata.normalize("NFC", text)
    value = html.unescape(value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line) + "\n"


def normalized_sha256(text: str) -> str:
    return sha256_bytes(normalize_text(text).encode("utf-8"))


def html_visible_text(path: Path) -> str:
    try:
        document = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ReproducibilityError(f"HTML illeggibile: {path}") from error
    parser = VisibleTextParser()
    parser.feed(document)
    return "\n".join(parser.parts)


def epub_visible_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = sorted(
                name
                for name in archive.namelist()
                if name.lower().endswith((".html", ".xhtml", ".htm"))
            )
            if not names:
                raise ReproducibilityError(
                    "EPUB privo di contenuti HTML/XHTML verificabili."
                )
            parts: list[str] = []
            for name in names:
                try:
                    document = archive.read(name).decode("utf-8")
                except (UnicodeError, KeyError) as error:
                    raise ReproducibilityError(
                        f"Contenuto EPUB non leggibile come UTF-8: {name}"
                    ) from error
                parser = VisibleTextParser()
                parser.feed(document)
                parts.extend(parser.parts)
            return "\n".join(parts)
    except zipfile.BadZipFile as error:
        raise ReproducibilityError(f"EPUB non valido: {path}") from error


def pdf_visible_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        raise ReproducibilityError(
            "pdftotext non è disponibile: impossibile verificare l'identità contenutistica PDF."
        )

    with tempfile.TemporaryDirectory(prefix="gyte-repro-") as temporary:
        output = Path(temporary) / "pdf.txt"
        completed = subprocess.run(
            [pdftotext, "-nopgbrk", str(path), str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ReproducibilityError(
                "Estrazione testuale PDF fallita."
                + (f" Dettaglio: {detail}" if detail else "")
            )
        try:
            return output.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise ReproducibilityError("Output pdftotext illeggibile.") from error


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReproducibilityError(f"Manifest illeggibile: {path}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise ReproducibilityError("È richiesto un publication-manifest v2.")
    return payload


def confined_artifact(manifest_dir: Path, record: Any, label: str) -> Path:
    if not isinstance(record, dict):
        raise ReproducibilityError(f"Record manifest mancante: {label}")
    value = record.get("path")
    if not isinstance(value, str) or not value:
        raise ReproducibilityError(f"Percorso manifest non valido: {label}")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReproducibilityError(f"Percorso manifest non confinato: {label}")
    path = (manifest_dir / relative).resolve(strict=False)
    base = manifest_dir.resolve(strict=False)
    try:
        path.relative_to(base)
    except ValueError as error:
        raise ReproducibilityError(f"Percorso manifest fuori directory: {label}") from error
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise ReproducibilityError(f"Artefatto assente, vuoto o symlink: {label}")
    return path


def build_report(manifest_path: Path) -> ReproducibilityReport:
    manifest_path = manifest_path.expanduser().resolve()
    manifest = read_manifest(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ReproducibilityError("Manifest privo di files valido.")

    reviewed = manifest.get("reviewed_source")
    if not isinstance(reviewed, dict):
        raise ReproducibilityError("Manifest privo di reviewed_source valido.")
    reviewed_hash = reviewed.get("sha256")
    if not isinstance(reviewed_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", reviewed_hash):
        raise ReproducibilityError("reviewed_source.sha256 non valido.")

    directory = manifest_path.parent
    paths = {
        name: confined_artifact(directory, files.get(name), f"files.{name}")
        for name in ("markdown", "html", "pdf", "epub")
    }

    markdown_bytes = paths["markdown"].read_bytes()
    html_bytes = paths["html"].read_bytes()

    artifacts = {
        "markdown": ArtifactIdentity(
            format="markdown",
            level="byte-reproducible",
            byte_sha256=sha256_bytes(markdown_bytes),
            normalized_sha256=sha256_bytes(markdown_bytes),
        ),
        "html": ArtifactIdentity(
            format="html",
            level="byte-reproducible",
            byte_sha256=sha256_bytes(html_bytes),
            normalized_sha256=sha256_bytes(html_bytes),
        ),
        "pdf": ArtifactIdentity(
            format="pdf",
            level="content-reproducible",
            byte_sha256=sha256_file(paths["pdf"]),
            normalized_sha256=normalized_sha256(pdf_visible_text(paths["pdf"])),
        ),
        "epub": ArtifactIdentity(
            format="epub",
            level="content-reproducible",
            byte_sha256=sha256_file(paths["epub"]),
            normalized_sha256=normalized_sha256(epub_visible_text(paths["epub"])),
        ),
    }

    # Existing manifest hashes are explicitly byte identities. Verify them.
    for name, identity in artifacts.items():
        record = files[name]
        expected = record.get("sha256")
        if expected != identity.byte_sha256:
            raise ReproducibilityError(
                f"files.{name}.sha256 non corrisponde ai byte correnti."
            )

    if artifacts["markdown"].byte_sha256 != reviewed_hash:
        raise ReproducibilityError(
            "La copia Markdown non corrisponde allo snapshot reviewed_source."
        )

    return ReproducibilityReport(
        manifest_path=manifest_path,
        reviewed_source_sha256=reviewed_hash,
        artifacts=artifacts,
    )


def compare_reports(
    left: ReproducibilityReport,
    right: ReproducibilityReport,
) -> dict[str, Any]:
    if left.reviewed_source_sha256 != right.reviewed_source_sha256:
        return {
            "equivalent_input": False,
            "reproducible": False,
            "reason": "reviewed-source-mismatch",
            "formats": {},
        }

    formats: dict[str, Any] = {}
    reproducible = True
    for name in ("markdown", "html", "pdf", "epub"):
        left_identity = left.artifacts[name]
        right_identity = right.artifacts[name]
        if left_identity.level == "byte-reproducible":
            match = left_identity.byte_sha256 == right_identity.byte_sha256
            compared = "byte_sha256"
        else:
            match = left_identity.normalized_sha256 == right_identity.normalized_sha256
            compared = "normalized_sha256"
        formats[name] = {
            "level": left_identity.level,
            "compared_identity": compared,
            "match": match,
            "byte_identical": left_identity.byte_sha256 == right_identity.byte_sha256,
        }
        reproducible = reproducible and match

    return {
        "equivalent_input": True,
        "reproducible": reproducible,
        "reason": None if reproducible else "format-identity-mismatch",
        "formats": formats,
    }


def report_to_dict(report: ReproducibilityReport) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest": str(report.manifest_path),
        "reviewed_source_sha256": report.reviewed_source_sha256,
        "manifest_semantics": {
            "files.*.sha256": "byte-identity",
            "markdown": "byte-reproducible",
            "html": "byte-reproducible",
            "pdf": "content-reproducible",
            "epub": "content-reproducible",
        },
        "artifacts": {
            name: {
                "level": identity.level,
                "byte_sha256": identity.byte_sha256,
                "normalized_sha256": identity.normalized_sha256,
            }
            for name, identity in report.artifacts.items()
        },
    }
