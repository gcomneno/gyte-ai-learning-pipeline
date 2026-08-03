"""Transcript acquisition, normalization and analysis preparation."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import (
    InspectionError,
    atomic_write_text,
    load_state,
)


RAW_FILENAME = "transcript.raw.txt"
NORMALIZED_FILENAME = "transcript.normalized.txt"
ANALYSIS_TEXT_FILENAME = "transcript.analysis.txt"
ANALYSIS_MARKDOWN_FILENAME = "transcript.analysis.md"

STABLE_TRANSCRIPT_NAMES: frozenset[str] = frozenset(
    {
        RAW_FILENAME,
        NORMALIZED_FILENAME,
        ANALYSIS_TEXT_FILENAME,
    }
)


class PreparationError(RuntimeError):
    """Raised when a transcript cannot be prepared safely."""


@dataclass(frozen=True)
class PreparationResult:
    workdir: Path
    source_transcript_path: Path
    raw_path: Path
    normalized_path: Path
    analysis_text_path: Path
    analysis_markdown_path: Path
    raw_words: int
    normalized_words: int
    analysis_words: int
    source_mode: str
    reused: bool


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PreparationError(f"File richiesto assente: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise PreparationError(f"File JSON illeggibile: {path}") from error

    if not isinstance(payload, dict):
        raise PreparationError(f"Il file JSON non contiene un oggetto: {path}")

    return payload


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def count_file_words(path: Path) -> int:
    return count_words(path.read_text(encoding="utf-8"))


def is_nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def selected_caption(metadata: dict[str, Any]) -> dict[str, Any] | None:
    captions = metadata.get("captions")

    if not isinstance(captions, dict):
        return None

    selected = captions.get("selected")
    return selected if isinstance(selected, dict) else None


def locate_caption_transcript(
    workdir: Path,
    language: str,
) -> Path | None:
    suffix = f".{language}.txt"
    candidates = [
        path
        for path in workdir.glob(f"*{suffix}")
        if path.name not in STABLE_TRANSCRIPT_NAMES
        and path.is_file()
        and path.stat().st_size > 0
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def run_gyte_transcript(
    url: str,
    workdir: Path,
    language: str,
) -> None:
    executable = shutil.which("gyte-transcript")

    if executable is None:
        raise PreparationError(
            "gyte-transcript non è disponibile nel PATH."
        )

    environment = os.environ.copy()
    environment["YT_TRANSCRIPT_LANGS"] = language

    completed = subprocess.run(
        [
            executable,
            "--outdir",
            str(workdir),
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PreparationError(
            "gyte-transcript non ha completato l'estrazione."
            + (f" Dettaglio: {detail}" if detail else "")
        )


def run_reflow(source: Path, destination: Path) -> None:
    executable = shutil.which("gyte-reflow-text")

    if executable is None:
        raise PreparationError(
            "gyte-reflow-text non è disponibile nel PATH."
        )

    completed = subprocess.run(
        [
            executable,
            "--ai-friendly",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PreparationError(
            "gyte-reflow-text non ha completato il reflow."
            + (f" Dettaglio: {detail}" if detail else "")
        )

    if not completed.stdout.strip():
        raise PreparationError(
            "gyte-reflow-text ha prodotto un risultato vuoto."
        )

    atomic_write_text(destination, completed.stdout)


def build_analysis_markdown(
    metadata: dict[str, Any],
    analysis_text: str,
) -> str:
    video = metadata.get("video")
    source = metadata.get("source")
    caption = selected_caption(metadata)

    video = video if isinstance(video, dict) else {}
    source = source if isinstance(source, dict) else {}

    title = video.get("title") or "Video YouTube"
    channel = video.get("channel") or "non disponibile"
    url = source.get("webpage_url") or source.get("requested_url") or ""
    duration = (
        video.get("duration_string")
        or video.get("duration_seconds")
        or "non disponibile"
    )
    upload_date = video.get("upload_date") or "non disponibile"

    if caption is None:
        caption_description = "trascrizione locale"
    else:
        language = caption.get("language") or "non disponibile"
        origin = caption.get("source") or "non disponibile"
        caption_description = f"caption {origin} {language}"

    lines = [
        f"# {title} — transcript di lavoro",
        "",
        f"- Relatore/canale: {channel}",
        f"- Video: {url}",
        f"- Durata: {duration}",
        f"- Data pubblicazione: {upload_date}",
        f"- Fonte testuale: {caption_description}",
        (
            "- Stato: materiale privato di studio, "
            "non revisionato parola per parola"
        ),
        "",
        "## Transcript riorganizzato",
        "",
        analysis_text.rstrip(),
        "",
    ]

    return "\n".join(lines)


def update_pipeline_state(
    state_path: Path,
    video_id: str,
    source_transcript_path: Path,
    source_mode: str,
    raw_path: Path,
    normalized_path: Path,
    analysis_text_path: Path,
    analysis_markdown_path: Path,
    raw_words: int,
    normalized_words: int,
    analysis_words: int,
    reused: bool,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    stages = state.setdefault("stages", {})

    stages["transcribe"] = {
        "status": "complete",
        "completed_at": now,
        "source_mode": source_mode,
        "source_transcript": source_transcript_path.name,
    }
    stages["prepare"] = {
        "status": "complete",
        "completed_at": now,
        "reused_existing_outputs": reused,
        "outputs": {
            "raw": raw_path.name,
            "normalized": normalized_path.name,
            "analysis_text": analysis_text_path.name,
            "analysis_markdown": analysis_markdown_path.name,
        },
        "word_counts": {
            "raw": raw_words,
            "normalized": normalized_words,
            "analysis": analysis_words,
        },
    }

    state["schema_version"] = 1
    state["video_id"] = video_id
    state["updated_at"] = now

    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def prepare_transcript(
    workdir: Path,
    force: bool = False,
) -> PreparationResult:
    workdir = workdir.expanduser().resolve()
    metadata_path = workdir / "metadata.json"
    state_path = workdir / "pipeline-state.json"

    metadata = read_json_object(metadata_path)
    video = metadata.get("video")
    source = metadata.get("source")

    if not isinstance(video, dict):
        raise PreparationError("Sezione video assente nei metadati.")

    if not isinstance(source, dict):
        raise PreparationError("Sezione source assente nei metadati.")

    video_id = video.get("id")
    url = source.get("requested_url") or source.get("webpage_url")

    if not isinstance(video_id, str) or not video_id:
        raise PreparationError("ID video assente nei metadati.")

    if not isinstance(url, str) or not url:
        raise PreparationError("URL sorgente assente nei metadati.")

    raw_path = workdir / RAW_FILENAME
    normalized_path = workdir / NORMALIZED_FILENAME
    analysis_text_path = workdir / ANALYSIS_TEXT_FILENAME
    analysis_markdown_path = workdir / ANALYSIS_MARKDOWN_FILENAME

    stable_outputs = (
        raw_path,
        normalized_path,
        analysis_text_path,
        analysis_markdown_path,
    )

    caption = selected_caption(metadata)
    language = (
        caption.get("language")
        if isinstance(caption, dict)
        else None
    )

    if (
        not force
        and all(is_nonempty_file(path) for path in stable_outputs)
    ):
        source_transcript_path = (
            locate_caption_transcript(workdir, language)
            if isinstance(language, str) and language
            else None
        )
        source_transcript_path = source_transcript_path or raw_path

        raw_words = count_file_words(raw_path)
        normalized_words = count_file_words(normalized_path)
        analysis_words = count_file_words(analysis_text_path)

        if normalized_words != analysis_words:
            raise PreparationError(
                "Gli output esistenti non superano il controllo parole: "
                f"normalizzato={normalized_words}, "
                f"analysis={analysis_words}."
            )

        update_pipeline_state(
            state_path=state_path,
            video_id=video_id,
            source_transcript_path=source_transcript_path,
            source_mode="adopted-existing",
            raw_path=raw_path,
            normalized_path=normalized_path,
            analysis_text_path=analysis_text_path,
            analysis_markdown_path=analysis_markdown_path,
            raw_words=raw_words,
            normalized_words=normalized_words,
            analysis_words=analysis_words,
            reused=True,
        )

        return PreparationResult(
            workdir=workdir,
            source_transcript_path=source_transcript_path,
            raw_path=raw_path,
            normalized_path=normalized_path,
            analysis_text_path=analysis_text_path,
            analysis_markdown_path=analysis_markdown_path,
            raw_words=raw_words,
            normalized_words=normalized_words,
            analysis_words=analysis_words,
            source_mode="adopted-existing",
            reused=True,
        )

    source_transcript_path: Path | None = None
    source_mode = ""

    if not force and is_nonempty_file(raw_path):
        source_transcript_path = raw_path
        source_mode = "stable-existing"
    elif isinstance(language, str) and language:
        source_transcript_path = locate_caption_transcript(
            workdir,
            language,
        )

        if source_transcript_path is not None:
            source_mode = "existing-caption"
        else:
            run_gyte_transcript(url, workdir, language)
            source_transcript_path = locate_caption_transcript(
                workdir,
                language,
            )
            source_mode = "generated-caption"
    else:
        raise PreparationError(
            "Nessuna caption utilizzabile e fallback audio "
            "non ancora implementato."
        )

    if source_transcript_path is None:
        raise PreparationError(
            "gyte-transcript non ha prodotto un transcript individuabile."
        )

    if source_transcript_path != raw_path:
        raw_content = source_transcript_path.read_text(encoding="utf-8")
        atomic_write_text(raw_path, raw_content)

    raw_text = raw_path.read_text(encoding="utf-8")
    normalized_text = html.unescape(raw_text)
    atomic_write_text(normalized_path, normalized_text)

    run_reflow(normalized_path, analysis_text_path)

    analysis_text = analysis_text_path.read_text(encoding="utf-8")
    analysis_markdown = build_analysis_markdown(
        metadata,
        analysis_text,
    )
    atomic_write_text(analysis_markdown_path, analysis_markdown)

    raw_words = count_words(raw_text)
    normalized_words = count_words(normalized_text)
    analysis_words = count_words(analysis_text)

    if normalized_words != analysis_words:
        raise PreparationError(
            "Il reflow ha modificato il conteggio delle parole: "
            f"normalizzato={normalized_words}, "
            f"analysis={analysis_words}."
        )

    update_pipeline_state(
        state_path=state_path,
        video_id=video_id,
        source_transcript_path=source_transcript_path,
        source_mode=source_mode,
        raw_path=raw_path,
        normalized_path=normalized_path,
        analysis_text_path=analysis_text_path,
        analysis_markdown_path=analysis_markdown_path,
        raw_words=raw_words,
        normalized_words=normalized_words,
        analysis_words=analysis_words,
        reused=False,
    )

    return PreparationResult(
        workdir=workdir,
        source_transcript_path=source_transcript_path,
        raw_path=raw_path,
        normalized_path=normalized_path,
        analysis_text_path=analysis_text_path,
        analysis_markdown_path=analysis_markdown_path,
        raw_words=raw_words,
        normalized_words=normalized_words,
        analysis_words=analysis_words,
        source_mode=source_mode,
        reused=False,
    )
