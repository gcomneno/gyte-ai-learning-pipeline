"""YouTube inspection and private workspace preparation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import os
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_WORK_ROOT = Path(
    os.environ.get(
        "GYTE_STUDY_WORK_ROOT",
        str(
            Path.home()
            / ".local"
            / "share"
            / "gyte-study-private-material"
        ),
    )
).expanduser()
PREFERRED_CAPTION_LANGUAGES: tuple[str, ...] = ("it-orig", "it")


class InspectionError(RuntimeError):
    """Raised when a video cannot be inspected safely."""


@dataclass(frozen=True)
class CaptionChoice:
    language: str
    source: str
    formats: tuple[str, ...]


@dataclass(frozen=True)
class InspectionResult:
    workdir: Path
    metadata_path: Path
    state_path: Path
    record: dict[str, Any]


def slugify(title: str, maximum_length: int = 100) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title)
    slug = slug.strip("-").lower()
    return slug[:maximum_length].rstrip("-") or "youtube-video"


def normalize_upload_date(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None

    if re.fullmatch(r"\d{8}", value):
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"

    return value


def available_formats(entries: object) -> tuple[str, ...]:
    if not isinstance(entries, list):
        return ()

    formats = {
        entry.get("ext")
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("ext"), str)
    }
    return tuple(sorted(formats))


def choose_caption(metadata: dict[str, Any]) -> CaptionChoice | None:
    manual = metadata.get("subtitles")
    automatic = metadata.get("automatic_captions")

    manual = manual if isinstance(manual, dict) else {}
    automatic = automatic if isinstance(automatic, dict) else {}

    for language in PREFERRED_CAPTION_LANGUAGES:
        if language in manual:
            return CaptionChoice(
                language=language,
                source="manual",
                formats=available_formats(manual[language]),
            )

        if language in automatic:
            return CaptionChoice(
                language=language,
                source="automatic",
                formats=available_formats(automatic[language]),
            )

    return None


def fetch_metadata(url: str) -> dict[str, Any]:
    executable = shutil.which("yt-dlp")

    if executable is None:
        raise InspectionError("yt-dlp non è disponibile nel PATH.")

    command = [
        executable,
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        url,
    ]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise InspectionError(
            "yt-dlp non ha recuperato i metadati."
            + (f" Dettaglio: {detail}" if detail else "")
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise InspectionError(
            "yt-dlp ha restituito metadati JSON non validi."
        ) from error

    if not isinstance(payload, dict):
        raise InspectionError("Il payload dei metadati non è un oggetto JSON.")

    if not isinstance(payload.get("id"), str) or not payload["id"]:
        raise InspectionError("ID del video assente nei metadati.")

    if not isinstance(payload.get("title"), str) or not payload["title"]:
        raise InspectionError("Titolo del video assente nei metadati.")

    return payload


def read_existing_video_id(metadata_path: Path) -> str | None:
    if not metadata_path.is_file():
        return None

    try:
        record = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InspectionError(
            f"Metadati esistenti illeggibili: {metadata_path}"
        ) from error

    video = record.get("video") if isinstance(record, dict) else None
    video_id = video.get("id") if isinstance(video, dict) else None
    return video_id if isinstance(video_id, str) else None


def choose_workdir(root: Path, title: str, video_id: str) -> Path:
    base = root / slugify(title)
    existing_id = read_existing_video_id(base / "metadata.json")

    if existing_id is None or existing_id == video_id:
        return base

    return root / f"{slugify(title)}-{video_id}"


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a text file without a predictable temporary name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": 1,
            "stages": {},
        }

    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InspectionError(
            f"File di stato esistente illeggibile: {path}"
        ) from error

    if not isinstance(state, dict):
        raise InspectionError(f"File di stato non valido: {path}")

    if not isinstance(state.get("stages"), dict):
        state["stages"] = {}

    return state


def build_record(
    url: str,
    metadata: dict[str, Any],
    selected_caption: CaptionChoice | None,
    inspected_at: str,
) -> dict[str, Any]:
    manual = metadata.get("subtitles")
    automatic = metadata.get("automatic_captions")

    manual_languages = sorted(manual) if isinstance(manual, dict) else []
    automatic_languages = (
        sorted(automatic) if isinstance(automatic, dict) else []
    )

    duration = metadata.get("duration")
    duration_seconds = (
        int(duration)
        if isinstance(duration, (int, float))
        else None
    )

    return {
        "schema_version": 1,
        "inspected_at": inspected_at,
        "source": {
            "requested_url": url,
            "webpage_url": metadata.get("webpage_url") or url,
        },
        "video": {
            "id": metadata["id"],
            "title": metadata["title"],
            "channel": metadata.get("channel"),
            "duration_seconds": duration_seconds,
            "duration_string": metadata.get("duration_string"),
            "language": metadata.get("language"),
            "original_language": metadata.get("original_language"),
            "upload_date": normalize_upload_date(
                metadata.get("upload_date")
            ),
        },
        "captions": {
            "selected": (
                asdict(selected_caption)
                if selected_caption is not None
                else None
            ),
            "manual_languages": manual_languages,
            "automatic_languages": automatic_languages,
        },
    }


def inspect_video(url: str, work_root: Path) -> InspectionResult:
    metadata = fetch_metadata(url)
    video_id = metadata["id"]
    title = metadata["title"]
    selected_caption = choose_caption(metadata)
    inspected_at = datetime.now(timezone.utc).isoformat()

    work_root = work_root.expanduser().resolve()
    workdir = choose_workdir(work_root, title, video_id)
    workdir.mkdir(parents=True, exist_ok=True)

    metadata_path = workdir / "metadata.json"
    state_path = workdir / "pipeline-state.json"
    source_url_path = workdir / "source-url.txt"

    record = build_record(
        url=url,
        metadata=metadata,
        selected_caption=selected_caption,
        inspected_at=inspected_at,
    )

    state = load_state(state_path)
    state["schema_version"] = 1
    state["video_id"] = video_id
    state["updated_at"] = inspected_at
    state["stages"]["inspect"] = {
        "status": "complete",
        "completed_at": inspected_at,
    }

    atomic_write_text(
        metadata_path,
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(source_url_path, url + "\n")

    return InspectionResult(
        workdir=workdir,
        metadata_path=metadata_path,
        state_path=state_path,
        record=record,
    )
