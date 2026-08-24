"""Publish a reviewed source lesson as semantic HTML, PDF and EPUB."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state


DEFAULT_AUTHOR = "Giancarlo e ChatGPT"
BACKTICK = chr(96)
MARKDOWN_FENCE = BACKTICK * 3
MANIFEST_SCHEMA_VERSION = 2
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
PREPARED_ANALYSIS_NAMES = (
    "transcript.analysis.md",
    "article.analysis.md",
    "transcript.analysis.txt",
)


class PublicationError(RuntimeError):
    """Raised when publication cannot be completed safely."""


@dataclass(frozen=True)
class ConversionMetrics:
    source_words: int
    pdf_words: int
    epub_words: int


@dataclass(frozen=True)
class PublicationResult:
    workdir: Path
    source_path: Path
    markdown_path: Path
    html_path: Path
    pdf_path: Path
    epub_path: Path
    manifest_path: Path
    title: str
    author: str
    metrics: ConversionMetrics
    backups: dict[str, str]


class VisibleTextParser(HTMLParser):
    """Collect visible textual content from generated HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"style", "script"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.hidden_depth > 0:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0 and data.strip():
            self.parts.append(data)


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def extract_heading(markdown: str) -> str:
    headings = [
        match.group(1).strip()
        for line in markdown.splitlines()
        if (match := re.match(r"^#\s+(.+?)\s*$", line))
    ]

    if len(headings) != 1:
        raise PublicationError(
            "La lezione sorgente deve contenere esattamente un titolo Markdown H1."
        )

    return headings[0]


def normalize_publication_title(heading: str) -> str:
    """Keep the reviewed H1 unchanged when deriving publication metadata."""
    return heading.strip()


def filename_stem(title: str) -> str:
    value = title.replace("—", "-")
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .-")
    return value or "lesson"


def render_inline(text: str) -> str:
    code_tokens: list[str] = []
    code_pattern = re.compile(
        re.escape(BACKTICK) + r"([^" + re.escape(BACKTICK) + r"]+)"
        + re.escape(BACKTICK)
    )

    def protect_code(match: re.Match[str]) -> str:
        token = f"@@GYTE_CODE_{len(code_tokens)}@@"
        code_tokens.append(
            "<code>" + html.escape(match.group(1), quote=False) + "</code>"
        )
        return token

    protected = code_pattern.sub(protect_code, text)
    rendered = html.escape(protected, quote=False)

    rendered = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        rendered,
    )
    rendered = re.sub(
        r"\*\*(.+?)\*\*",
        r"<strong>\1</strong>",
        rendered,
    )
    rendered = re.sub(
        r"(?<!\*)\*([^*]+?)\*(?!\*)",
        r"<em>\1</em>",
        rendered,
    )

    for index, code_html in enumerate(code_tokens):
        rendered = rendered.replace(
            f"@@GYTE_CODE_{index}@@",
            code_html,
        )

    return rendered


def starts_block(line: str) -> bool:
    stripped = line.lstrip()

    return bool(
        not stripped
        or stripped.startswith(MARKDOWN_FENCE)
        or re.match(r"^#{1,6}\s+", stripped)
        or re.match(r"^[-*_]\s*[-*_]\s*[-*_]", stripped)
        or stripped.startswith("> ")
        or re.match(r"^[-*+]\s+", stripped)
        or re.match(r"^\d+[.)]\s+", stripped)
    )


def render_markdown_body(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith(MARKDOWN_FENCE):
            language = stripped[len(MARKDOWN_FENCE):].strip()
            index += 1
            code_lines: list[str] = []

            while (
                index < len(lines)
                and not lines[index].strip().startswith(MARKDOWN_FENCE)
            ):
                code_lines.append(lines[index])
                index += 1

            if index < len(lines):
                index += 1

            language_class = (
                f' class="language-{html.escape(language)}"'
                if language
                else ""
            )
            code = html.escape("\n".join(code_lines), quote=False)
            output.append(
                f"<pre><code{language_class}>{code}</code></pre>"
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)

        if heading:
            level = len(heading.group(1))
            output.append(
                f"<h{level}>{render_inline(heading.group(2))}</h{level}>"
            )
            index += 1
            continue

        if re.match(r"^[-*_]\s*[-*_]\s*[-*_]", stripped):
            output.append("<hr>")
            index += 1
            continue

        if stripped.startswith("> "):
            quote_lines: list[str] = []

            while index < len(lines):
                current = lines[index].strip()

                if not current.startswith(">"):
                    break

                quote_lines.append(current[1:].lstrip())
                index += 1

            quote_text = " ".join(quote_lines)
            output.append(
                "<blockquote><p>"
                + render_inline(quote_text)
                + "</p></blockquote>"
            )
            continue

        if re.match(r"^[-*+]\s+", stripped):
            items: list[str] = []

            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^[-*+]\s+(.+)$", current)

                if not match:
                    break

                items.append(
                    "<li>" + render_inline(match.group(1)) + "</li>"
                )
                index += 1

            output.append("<ul>" + "".join(items) + "</ul>")
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            items = []

            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^\d+[.)]\s+(.+)$", current)

                if not match:
                    break

                items.append(
                    "<li>" + render_inline(match.group(1)) + "</li>"
                )
                index += 1

            output.append("<ol>" + "".join(items) + "</ol>")
            continue

        paragraph_lines = [stripped]
        index += 1

        while index < len(lines) and not starts_block(lines[index]):
            paragraph_lines.append(lines[index].strip())
            index += 1

        paragraph = " ".join(part for part in paragraph_lines if part)
        output.append("<p>" + render_inline(paragraph) + "</p>")

    return "\n".join(output)


def render_document(
    markdown: str,
    title: str,
    author: str,
) -> str:
    body = render_markdown_body(markdown)

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="author" content="{html.escape(author, quote=True)}">
  <title>{html.escape(title)}</title>
  <style>
    @page {{
      margin: 18mm 17mm 20mm;
    }}

    body {{
      font-family: serif;
      font-size: 1em;
      line-height: 1.55;
      max-width: 42em;
      margin: 0 auto;
      padding: 1.5em;
    }}

    h1, h2, h3 {{
      line-height: 1.2;
      page-break-after: avoid;
    }}

    h1 {{
      margin-bottom: 1.3em;
    }}

    h2 {{
      margin-top: 1.7em;
    }}

    p, li {{
      orphans: 3;
      widows: 3;
    }}

    blockquote {{
      border-left: 0.25em solid #888;
      margin-left: 0;
      padding-left: 1em;
      font-style: italic;
    }}

    code {{
      font-family: monospace;
    }}

    pre {{
      white-space: pre-wrap;
      padding: 0.8em;
      border: 1px solid #aaa;
    }}

    a {{
      color: inherit;
      text-decoration: underline;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def visible_html_text(document: str) -> str:
    parser = VisibleTextParser()
    parser.feed(document)
    return "\n".join(parser.parts)


def run_command(command: list[str], description: str) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PublicationError(
            f"{description}."
            + (f" Dettaglio: {detail}" if detail else "")
        )


def validate_epub(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            damaged = archive.testzip()

            if damaged is not None:
                raise PublicationError(
                    f"Elemento EPUB danneggiato: {damaged}"
                )

            if "mimetype" not in archive.namelist():
                raise PublicationError(
                    "Il file EPUB non contiene mimetype."
                )

            mimetype = archive.read("mimetype").decode(
                "ascii",
                errors="replace",
            ).strip()

            if mimetype != "application/epub+zip":
                raise PublicationError(
                    f"Mimetype EPUB inatteso: {mimetype}"
                )
    except zipfile.BadZipFile as error:
        raise PublicationError(
            "Il file prodotto non è un archivio EPUB valido."
        ) from error


def path_is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PublicationError(f"{label} assente: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PublicationError(f"{label} illeggibile: {path}") from error

    if not isinstance(value, dict):
        raise PublicationError(f"{label} non contiene un oggetto JSON: {path}")

    return value


def observed_json_object(path: Path) -> tuple[dict[str, Any], str] | None:
    if not path.is_file() or path.is_symlink():
        return None

    try:
        content = path.read_bytes()
        value = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None

    if not isinstance(value, dict):
        return None

    return value, hashlib.sha256(content).hexdigest()


def source_identity(
    metadata: dict[str, Any] | None,
    state: dict[str, Any],
) -> tuple[str, str, str]:
    source_type = None
    if metadata is not None and isinstance(metadata.get("source_type"), str):
        source_type = metadata["source_type"]
    elif isinstance(state.get("source_type"), str):
        source_type = state["source_type"]

    if source_type == "article":
        source_id = state.get("source_id")
        return (
            "article",
            "article-source-id",
            source_id if isinstance(source_id, str) and source_id else "unavailable",
        )

    video_id = None
    if metadata is not None:
        video = metadata.get("video")
        if isinstance(video, dict) and isinstance(video.get("id"), str):
            video_id = video["id"]
    if video_id is None and isinstance(state.get("video_id"), str):
        video_id = state["video_id"]

    return (
        source_type if isinstance(source_type, str) and source_type else "youtube",
        "youtube-video-id",
        video_id if isinstance(video_id, str) and video_id else "unavailable",
    )


def safe_relative_name(path: Path, base: Path) -> str:
    try:
        relative = path.relative_to(base)
    except ValueError:
        return path.name

    value = relative.as_posix()
    return path.name if value.startswith("../") else value


def build_source_context(workdir: Path, state: dict[str, Any]) -> dict[str, Any]:
    metadata_observation = observed_json_object(workdir / "metadata.json")
    metadata = metadata_observation[0] if metadata_observation is not None else None
    source_type, source_id_kind, source_id = source_identity(metadata, state)
    context: dict[str, Any] = {
        "relationship": "observed-at-publication-time",
        "source_type": source_type,
        "source_id_kind": source_id_kind,
        "source_id": source_id,
        "prepared_artifacts": [],
    }
    if metadata_observation is not None:
        context["metadata_sha256"] = metadata_observation[1]

    prepared_artifacts: list[dict[str, str]] = []
    for name in PREPARED_ANALYSIS_NAMES:
        artifact = workdir / name
        if artifact.is_file() and not artifact.is_symlink():
            prepared_artifacts.append(
                {
                    "role": "prepared-analysis",
                    "name": safe_relative_name(artifact, workdir),
                    "sha256": sha256_file(artifact),
                }
            )
    context["prepared_artifacts"] = prepared_artifacts
    return context


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PublicationError(f"{label} non è uno SHA-256 valido.")
    return value


def confined_relative_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PublicationError(f"{label} deve essere un percorso relativo non vuoto.")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise PublicationError(f"{label} deve restare relativo e confinato.")
    if any(part in {"", "."} for part in relative.parts):
        raise PublicationError(f"{label} contiene segmenti non validi.")

    try:
        resolved_base = base.resolve(strict=False)
        resolved_path = (base / relative).resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise PublicationError(f"{label} non è risolvibile.") from error

    if not path_is_within(resolved_path, resolved_base):
        raise PublicationError(f"{label} esce dalla directory di pubblicazione.")
    return resolved_path


def validate_regular_file_hash(path: Path, expected_hash: str, label: str) -> None:
    if path.is_symlink():
        raise PublicationError(f"{label} non può essere un symlink.")
    try:
        if not path.is_file() or path.stat().st_size == 0:
            raise PublicationError(f"{label} assente o vuoto: {path}")
        actual_hash = sha256_file(path)
    except OSError as error:
        raise PublicationError(f"{label} illeggibile: {path}") from error
    if actual_hash != expected_hash:
        raise PublicationError(f"{label} non corrisponde allo SHA-256 del manifest.")


def validate_source_context(
    manifest: dict[str, Any],
    *,
    workdir: Path | None,
    full_validation: bool,
) -> None:
    context = manifest.get("source_context")
    if not isinstance(context, dict):
        raise PublicationError("Il manifest non contiene source_context valido.")
    if context.get("relationship") != "observed-at-publication-time":
        raise PublicationError("source_context.relationship non valido.")
    for field in ("source_type", "source_id_kind", "source_id"):
        if not isinstance(context.get(field), str) or not context[field]:
            raise PublicationError(f"source_context.{field} non valido.")
    if "metadata_sha256" in context:
        metadata_hash = require_sha256(
            context["metadata_sha256"],
            "source_context.metadata_sha256",
        )
        if workdir is not None and full_validation:
            validate_regular_file_hash(
                workdir / "metadata.json",
                metadata_hash,
                "metadata.json",
            )

    prepared = context.get("prepared_artifacts")
    if not isinstance(prepared, list):
        raise PublicationError("source_context.prepared_artifacts non è una lista.")
    for index, artifact in enumerate(prepared):
        label = f"source_context.prepared_artifacts[{index}]"
        if not isinstance(artifact, dict):
            raise PublicationError(f"{label} non è un oggetto.")
        if artifact.get("role") != "prepared-analysis":
            raise PublicationError(f"{label}.role non valido.")
        name = artifact.get("name")
        require_sha256(artifact.get("sha256"), f"{label}.sha256")
        if workdir is None:
            if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
                raise PublicationError(f"{label}.name non è sicuro.")
            continue
        artifact_path = confined_relative_path(workdir, name, f"{label}.name")
        if full_validation:
            validate_regular_file_hash(artifact_path, artifact["sha256"], label)


def validate_manifest_files(
    manifest: dict[str, Any],
    manifest_dir: Path,
    *,
    expected_epub_path: Path | None,
    full_validation: bool,
) -> dict[str, Path]:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise PublicationError("Il manifest non contiene files valido.")

    expected = {
        "markdown": ("reviewed-source-copy", None),
        "html": ("derived-publication-html", "markdown"),
        "pdf": ("derived-publication-pdf", "html"),
        "epub": ("derived-publication-epub", "html"),
    }
    resolved: dict[str, Path] = {}

    for key, (role, derived_from) in expected.items():
        record = files.get(key)
        if not isinstance(record, dict):
            raise PublicationError(f"files.{key} mancante o non valido.")
        if record.get("role") != role:
            raise PublicationError(f"files.{key}.role non valido.")
        if derived_from is None:
            if "derived_from" in record:
                raise PublicationError(f"files.{key}.derived_from non ammesso.")
        elif record.get("derived_from") != derived_from:
            raise PublicationError(f"files.{key}.derived_from non valido.")
        expected_hash = require_sha256(record.get("sha256"), f"files.{key}.sha256")
        resolved_path = confined_relative_path(
            manifest_dir,
            record.get("path"),
            f"files.{key}.path",
        )
        resolved[key] = resolved_path

        if full_validation or key == "epub":
            validate_regular_file_hash(resolved_path, expected_hash, f"files.{key}")
            if key == "epub":
                try:
                    validate_epub(resolved_path)
                except PublicationError as error:
                    raise PublicationError("files.epub non è un EPUB valido.") from error

    if expected_epub_path is not None:
        try:
            expected_resolved = expected_epub_path.expanduser().resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise PublicationError("Percorso EPUB atteso non risolvibile.") from error
        if resolved["epub"] != expected_resolved:
            raise PublicationError(
                "Il percorso EPUB del manifest non corrisponde allo stato publish."
            )

    reviewed = manifest.get("reviewed_source")
    if not isinstance(reviewed, dict):
        raise PublicationError("Il manifest non contiene reviewed_source valido.")
    if reviewed.get("role") != "reviewed-source-snapshot":
        raise PublicationError("reviewed_source.role non valido.")
    if reviewed.get("copied_to") != "markdown":
        raise PublicationError("reviewed_source.copied_to non valido.")
    if not isinstance(reviewed.get("h1"), str) or not reviewed["h1"].strip():
        raise PublicationError("reviewed_source.h1 non valido.")
    reviewed_hash = require_sha256(reviewed.get("sha256"), "reviewed_source.sha256")
    markdown_hash = files["markdown"]["sha256"]
    if reviewed_hash != markdown_hash:
        raise PublicationError(
            "reviewed_source.sha256 non corrisponde a files.markdown.sha256."
        )

    return resolved


def validate_manifest_backups(manifest: dict[str, Any], manifest_dir: Path) -> None:
    backups = manifest.get("backups")
    if not isinstance(backups, dict):
        raise PublicationError("Il manifest non contiene backups valido.")
    for destination, backup in backups.items():
        confined_relative_path(manifest_dir, destination, "backups destination")
        confined_relative_path(manifest_dir, backup, "backups backup")


def validate_manifest_v2_structure(
    manifest_path: Path,
    *,
    workdir: Path | None,
    expected_epub_path: Path | None,
    full_validation: bool,
) -> dict[str, Any]:
    if manifest_path.is_symlink():
        raise PublicationError("Il manifest di pubblicazione non può essere un symlink.")
    manifest = read_json_object(manifest_path, "Manifest di pubblicazione")
    schema_version = manifest.get("schema_version")
    if type(schema_version) is not int or schema_version != MANIFEST_SCHEMA_VERSION:
        raise PublicationError(
            "Manifest di pubblicazione legacy/non supportato: "
            "ripubblicare per creare il manifest v2."
        )

    manifest_dir = manifest_path.parent.resolve(strict=False)
    for field in ("published_at", "title", "author"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise PublicationError(f"{field} non valido nel manifest.")
    if type(manifest.get("source_words")) is not int or manifest["source_words"] <= 0:
        raise PublicationError("source_words non valido nel manifest.")

    validate_source_context(
        manifest,
        workdir=workdir,
        full_validation=full_validation,
    )
    validate_manifest_files(
        manifest,
        manifest_dir,
        expected_epub_path=expected_epub_path,
        full_validation=full_validation,
    )
    validate_manifest_backups(manifest, manifest_dir)
    return manifest


def validate_publication_manifest(
    manifest_path: Path,
    *,
    workdir: Path | None = None,
    expected_epub_path: Path | None = None,
) -> dict[str, Any]:
    """Validate manifest v2 plus all current publication/provenance bytes."""
    return validate_manifest_v2_structure(
        manifest_path,
        workdir=workdir,
        expected_epub_path=expected_epub_path,
        full_validation=True,
    )


def validate_publication_manifest_for_delivery(
    manifest_path: Path,
    *,
    expected_epub_path: Path,
) -> dict[str, Any]:
    """Validate manifest v2 only for delivery authority over the EPUB."""
    return validate_manifest_v2_structure(
        manifest_path,
        workdir=None,
        expected_epub_path=expected_epub_path,
        full_validation=False,
    )


def build_converted_outputs(
    html_path: Path,
    pdf_path: Path,
    epub_path: Path,
    title: str,
    author: str,
    source_words: int,
    temporary_directory: Path,
) -> ConversionMetrics:
    ebook_convert = shutil.which("ebook-convert")
    pdftotext = shutil.which("pdftotext")

    if ebook_convert is None:
        raise PublicationError(
            "ebook-convert non è disponibile nel PATH."
        )

    if pdftotext is None:
        raise PublicationError(
            "pdftotext non è disponibile nel PATH."
        )

    run_command(
        [
            ebook_convert,
            str(html_path),
            str(epub_path),
            "--title",
            title,
            "--authors",
            author,
            "--language",
            "it",
        ],
        "Conversione HTML → EPUB fallita",
    )

    run_command(
        [
            ebook_convert,
            str(html_path),
            str(pdf_path),
            "--title",
            title,
            "--authors",
            author,
            "--language",
            "it",
        ],
        "Conversione HTML → PDF fallita",
    )

    if not epub_path.is_file() or epub_path.stat().st_size == 0:
        raise PublicationError("EPUB prodotto assente o vuoto.")

    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PublicationError("PDF prodotto assente o vuoto.")

    validate_epub(epub_path)

    epub_text = temporary_directory / "epub-roundtrip.txt"
    pdf_text = temporary_directory / "pdf-roundtrip.txt"

    run_command(
        [
            ebook_convert,
            str(epub_path),
            str(epub_text),
        ],
        "Estrazione testuale EPUB fallita",
    )
    run_command(
        [
            pdftotext,
            "-nopgbrk",
            str(pdf_path),
            str(pdf_text),
        ],
        "Estrazione testuale PDF fallita",
    )

    epub_words = count_words(
        epub_text.read_text(encoding="utf-8", errors="replace")
    )
    pdf_words = count_words(
        pdf_text.read_text(encoding="utf-8", errors="replace")
    )

    minimum_words = max(1, int(source_words * 0.85))

    if epub_words < minimum_words:
        raise PublicationError(
            "L'EPUB contiene troppo poco testo: "
            f"{epub_words} parole su almeno {minimum_words} attese."
        )

    if pdf_words < minimum_words:
        raise PublicationError(
            "Il PDF contiene troppo poco testo: "
            f"{pdf_words} parole su almeno {minimum_words} attese."
        )

    return ConversionMetrics(
        source_words=source_words,
        pdf_words=pdf_words,
        epub_words=epub_words,
    )


def next_backup_path(path: Path, timestamp: str) -> Path:
    candidate = path.with_name(
        f"{path.stem}.backup-{timestamp}{path.suffix}"
    )
    counter = 2

    while candidate.exists():
        candidate = path.with_name(
            f"{path.stem}.backup-{timestamp}-{counter}{path.suffix}"
        )
        counter += 1

    return candidate


def backup_existing(path: Path, timestamp: str) -> Path | None:
    if not path.exists():
        return None

    backup = next_backup_path(path, timestamp)
    path.replace(backup)
    return backup


def update_publish_state(
    state_path: Path,
    title: str,
    author: str,
    markdown_path: Path,
    html_path: Path,
    pdf_path: Path,
    epub_path: Path,
    manifest_path: Path,
    metrics: ConversionMetrics,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    stages = state.setdefault("stages", {})

    stages["publish"] = {
        "status": "complete",
        "completed_at": now,
        "title": title,
        "author": author,
        "outputs": {
            "markdown": str(markdown_path),
            "html": str(html_path),
            "pdf": str(pdf_path),
            "epub": str(epub_path),
            "manifest": str(manifest_path),
        },
        "word_counts": {
            "source": metrics.source_words,
            "pdf": metrics.pdf_words,
            "epub": metrics.epub_words,
        },
    }
    state["updated_at"] = now

    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def publish_lesson(
    workdir: Path,
    source_path: Path,
    author: str = DEFAULT_AUTHOR,
    output_dir: Path | None = None,
) -> PublicationResult:
    workdir = workdir.expanduser().resolve()
    source_path = source_path.expanduser().resolve()

    if not source_path.is_file():
        raise PublicationError(
            f"Lezione sorgente Markdown non trovata: {source_path}"
        )

    try:
        source_bytes = source_path.read_bytes()
        markdown = source_bytes.decode("utf-8")
    except UnicodeError as error:
        raise PublicationError(
            "La lezione sorgente Markdown deve essere UTF-8 valido."
        ) from error

    if not markdown.strip():
        raise PublicationError("La lezione sorgente Markdown è vuota.")

    heading = extract_heading(markdown)
    title = normalize_publication_title(heading)
    stem = filename_stem(title)

    publication_dir = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else workdir / "publication"
    )
    publication_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = publication_dir / f"{stem}.md"
    html_path = publication_dir / f"{stem}.html"
    pdf_path = publication_dir / f"{stem}.pdf"
    epub_path = publication_dir / f"{stem}.epub"
    manifest_path = publication_dir / "publication-manifest.json"
    state_path = workdir / "pipeline-state.json"

    html_document = render_document(markdown, title, author)
    source_words = count_words(visible_html_text(html_document))
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    if source_words == 0:
        raise PublicationError(
            "La sorgente HTML non contiene testo visibile."
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups: dict[str, str] = {}

    with tempfile.TemporaryDirectory(
        prefix=".gyte-publish-",
        dir=publication_dir,
    ) as temporary:
        temporary_directory = Path(temporary)
        temporary_html = temporary_directory / "lesson.html"
        temporary_pdf = temporary_directory / "lesson.pdf"
        temporary_epub = temporary_directory / "lesson.epub"

        temporary_html.write_text(
            html_document,
            encoding="utf-8",
        )

        metrics = build_converted_outputs(
            html_path=temporary_html,
            pdf_path=temporary_pdf,
            epub_path=temporary_epub,
            title=title,
            author=author,
            source_words=source_words,
            temporary_directory=temporary_directory,
        )

        for destination in (
            markdown_path,
            html_path,
            pdf_path,
            epub_path,
            manifest_path,
        ):
            backup = backup_existing(destination, timestamp)

            if backup is not None:
                backups[
                    safe_relative_name(destination, publication_dir)
                ] = safe_relative_name(backup, publication_dir)

        atomic_write_bytes(markdown_path, source_bytes)
        atomic_write_text(html_path, html_document)
        temporary_pdf.replace(pdf_path)
        temporary_epub.replace(epub_path)

    now = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    markdown_sha256 = sha256_file(markdown_path)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "published_at": now,
        "title": title,
        "author": author,
        "source_context": build_source_context(workdir, state),
        "reviewed_source": {
            "role": "reviewed-source-snapshot",
            "sha256": source_sha256,
            "copied_to": "markdown",
            "h1": heading,
        },
        "files": {
            "markdown": {
                "path": markdown_path.name,
                "role": "reviewed-source-copy",
                "sha256": markdown_sha256,
            },
            "html": {
                "path": html_path.name,
                "role": "derived-publication-html",
                "derived_from": "markdown",
                "sha256": sha256_file(html_path),
            },
            "pdf": {
                "path": pdf_path.name,
                "role": "derived-publication-pdf",
                "derived_from": "html",
                "sha256": sha256_file(pdf_path),
                "words": metrics.pdf_words,
            },
            "epub": {
                "path": epub_path.name,
                "role": "derived-publication-epub",
                "derived_from": "html",
                "sha256": sha256_file(epub_path),
                "words": metrics.epub_words,
            },
        },
        "source_words": metrics.source_words,
        "backups": backups,
    }

    atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    validate_publication_manifest(
        manifest_path,
        workdir=workdir,
        expected_epub_path=epub_path,
    )

    update_publish_state(
        state_path=state_path,
        title=title,
        author=author,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        epub_path=epub_path,
        manifest_path=manifest_path,
        metrics=metrics,
    )

    return PublicationResult(
        workdir=workdir,
        source_path=source_path,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        epub_path=epub_path,
        manifest_path=manifest_path,
        title=title,
        author=author,
        metrics=metrics,
        backups=backups,
    )
