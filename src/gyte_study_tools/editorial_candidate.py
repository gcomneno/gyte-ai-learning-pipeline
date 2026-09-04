"""Private editorial-candidate generation from prepared analysis."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state


CANDIDATE_FILENAME = "editorial-candidate.md"
CANDIDATE_RECORD_FILENAME = "editorial-candidate.json"


class EditorialCandidateError(RuntimeError):
    """Raised when an editorial candidate cannot be generated safely."""


@dataclass(frozen=True)
class EditorialCandidateResult:
    workdir: Path
    candidate_path: Path
    record_path: Path
    candidate_sha256: str
    input_sha256: str
    reused: bool


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


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


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EditorialCandidateError(f"{label} illeggibile: {path}") from error
    if not isinstance(value, dict):
        raise EditorialCandidateError(f"{label} non contiene un oggetto JSON.")
    return value


def require_prepare_complete(state: dict[str, Any]) -> None:
    stages = state.get("stages")
    prepare = stages.get("prepare") if isinstance(stages, dict) else None
    if not isinstance(prepare, dict) or prepare.get("status") != "complete":
        raise EditorialCandidateError(
            "La fase prepare deve essere complete prima della generazione del candidate."
        )


def canonical_input(workdir: Path, state: dict[str, Any]) -> tuple[str, Path]:
    source_type = state.get("source_type")
    if source_type == "article":
        name = "article.analysis.md"
    else:
        name = "transcript.analysis.md"
    path = workdir / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise EditorialCandidateError(
            f"Prepared analysis assente, vuota o non regolare: {path}"
        )
    return name, path


def source_title(workdir: Path, state: dict[str, Any]) -> str:
    metadata = read_json(workdir / "metadata.json", "metadata.json")
    if state.get("source_type") == "article":
        article = metadata.get("article")
        if isinstance(article, dict) and isinstance(article.get("title"), str):
            return article["title"].strip() or "Source lesson candidate"
        return "Source lesson candidate"
    video = metadata.get("video")
    if isinstance(video, dict) and isinstance(video.get("title"), str):
        return video["title"].strip() or "Source lesson candidate"
    return "Source lesson candidate"


def demote_embedded_headings(markdown: str) -> str:
    """Prevent embedded prepared-analysis headings from competing with candidate H1."""
    lines: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match is None:
            lines.append(line)
            continue
        level = min(6, len(match.group(1)) + 2)
        lines.append(f"{'#' * level} {match.group(2)}")
    return "\n".join(lines)


def render_candidate(title: str, prepared: str) -> str:
    embedded = demote_embedded_headings(prepared)
    return (
        f"# {title}\n\n"
        "> Editorial candidate — private derived material. This artifact is not a reviewed source lesson and has no publication authority until an explicit review checkpoint is recorded over its exact bytes.\n\n"
        "## Purpose / central thesis\n\n"
        "Refine the prepared source material below into a self-contained reviewed source lesson.\n\n"
        "## Prepared source material\n\n"
        f"{embedded.rstrip()}\n\n"
        "## Editorial work required\n\n"
        "- separate source facts, source interpretations and critical assessment;\n"
        "- rework examples without reproducing unnecessary transcript material;\n"
        "- add practical applications;\n"
        "- make limitations and unsupported claims explicit;\n"
        "- add review or reflection questions;\n"
        "- fact-check claims that require external verification before review approval.\n"
    )


def valid_reusable_record(
    record_path: Path,
    candidate_path: Path,
    input_name: str,
    input_sha256: str,
    input_bytes: int,
) -> dict[str, Any] | None:
    if record_path.is_symlink() or candidate_path.is_symlink():
        return None
    if not record_path.is_file() or not candidate_path.is_file():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        candidate_bytes = candidate_path.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return None
    if (
        record.get("schema_version") != 1
        or record.get("artifact") != "editorial-candidate"
        or record.get("authority") != "candidate"
        or record.get("status") != "complete"
        or provenance.get("canonical_input") != input_name
        or provenance.get("canonical_input_sha256") != input_sha256
        or provenance.get("canonical_input_byte_count") != input_bytes
        or record.get("candidate_sha256") != sha256_bytes(candidate_bytes)
        or not candidate_bytes
    ):
        return None
    return record


def update_candidate_state(
    state_path: Path,
    record_path: Path,
    candidate_path: Path,
    record: dict[str, Any],
    reused: bool,
) -> None:
    state = load_state(state_path)
    require_prepare_complete(state)
    stages = state.setdefault("stages", {})
    now = datetime.now(timezone.utc).isoformat()
    stages["candidate"] = {
        "status": "complete",
        "completed_at": now,
        "authority": "candidate",
        "candidate": candidate_path.name,
        "record": record_path.name,
        "candidate_sha256": record["candidate_sha256"],
        "input_sha256": record["provenance"]["canonical_input_sha256"],
        "reused": reused,
    }
    state["updated_at"] = now
    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def generate_editorial_candidate(
    workdir: Path,
    *,
    force: bool = False,
) -> EditorialCandidateResult:
    workdir = workdir.expanduser().resolve()
    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    require_prepare_complete(state)

    input_name, input_path = canonical_input(workdir, state)
    input_bytes_raw = input_path.read_bytes()
    try:
        prepared = input_bytes_raw.decode("utf-8")
    except UnicodeError as error:
        raise EditorialCandidateError("Prepared analysis deve essere UTF-8 valido.") from error
    input_sha256 = sha256_bytes(input_bytes_raw)
    input_bytes = len(input_bytes_raw)

    candidate_path = workdir / CANDIDATE_FILENAME
    record_path = workdir / CANDIDATE_RECORD_FILENAME

    if not force:
        reusable = valid_reusable_record(
            record_path,
            candidate_path,
            input_name,
            input_sha256,
            input_bytes,
        )
        if reusable is not None:
            update_candidate_state(
                state_path,
                record_path,
                candidate_path,
                reusable,
                reused=True,
            )
            return EditorialCandidateResult(
                workdir=workdir,
                candidate_path=candidate_path,
                record_path=record_path,
                candidate_sha256=reusable["candidate_sha256"],
                input_sha256=input_sha256,
                reused=True,
            )

    title = source_title(workdir, state)
    candidate = render_candidate(title, prepared)
    candidate_bytes = candidate.encode("utf-8")
    candidate_sha256 = sha256_bytes(candidate_bytes)
    record = {
        "schema_version": 1,
        "artifact": "editorial-candidate",
        "authority": "candidate",
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "canonical_input": input_name,
            "canonical_input_sha256": input_sha256,
            "canonical_input_byte_count": input_bytes,
        },
        "candidate": candidate_path.name,
        "candidate_sha256": candidate_sha256,
        "promotion": {
            "required_operation": "reviewed-source-checkpoint",
            "automatic": False,
        },
    }

    atomic_write_bytes(candidate_path, candidate_bytes)
    atomic_write_text(
        record_path,
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
    )
    update_candidate_state(
        state_path,
        record_path,
        candidate_path,
        record,
        reused=False,
    )
    return EditorialCandidateResult(
        workdir=workdir,
        candidate_path=candidate_path,
        record_path=record_path,
        candidate_sha256=candidate_sha256,
        input_sha256=input_sha256,
        reused=False,
    )
