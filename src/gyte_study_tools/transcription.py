"""Local-first audio transcription fallback for video sources."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


LOCAL_AUDIO_PREFIX = "transcription-source"
LOCAL_TRANSCRIPT_FILENAME = "transcription.local.txt"
WHISPER_OUTPUT_DIRNAME = ".whisper-output"


class LocalTranscriptionError(RuntimeError):
    """Raised when the local transcription fallback cannot complete safely."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class LocalTranscriptionResult:
    transcript_path: Path
    audio_path: Path
    reused_transcript: bool
    reused_audio: bool
    model: str


def _is_usable_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and path.stat().st_size > 0


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
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


def locate_local_audio(workdir: Path) -> Path | None:
    candidates = [
        path
        for path in workdir.iterdir()
        if path.name.startswith(f"{LOCAL_AUDIO_PREFIX}.")
        and not path.name.endswith((".part", ".ytdl", ".txt"))
        and _is_usable_regular_file(path)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _resolve_executable(name_or_path: str, label: str) -> str:
    candidate = Path(name_or_path).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        raise LocalTranscriptionError(
            "configuration",
            f"{label} non è eseguibile: {candidate}",
        )

    executable = shutil.which(name_or_path)
    if executable is None:
        raise LocalTranscriptionError(
            "configuration",
            f"{label} non è disponibile nel PATH: {name_or_path}",
        )
    return executable


def acquire_audio(url: str, workdir: Path) -> tuple[Path, bool]:
    existing = locate_local_audio(workdir)
    if existing is not None:
        return existing, True

    yt_dlp = _resolve_executable("yt-dlp", "yt-dlp")
    output_template = str(workdir / f"{LOCAL_AUDIO_PREFIX}.%(ext)s")
    completed = subprocess.run(
        [
            yt_dlp,
            "--no-playlist",
            "-f",
            "bestaudio/best",
            "-o",
            output_template,
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    detail = completed.stderr.strip() or completed.stdout.strip()
    if completed.returncode != 0:
        raise LocalTranscriptionError(
            "download",
            "yt-dlp non ha completato l'acquisizione audio."
            + (f" Dettaglio: {detail}" if detail else ""),
        )

    audio = locate_local_audio(workdir)
    if audio is None:
        raise LocalTranscriptionError(
            "download",
            "yt-dlp è terminato senza produrre un file audio privato utilizzabile.",
        )
    return audio, False


def transcribe_audio(audio_path: Path, workdir: Path) -> tuple[Path, str]:
    command = os.environ.get("GYTE_WHISPER_COMMAND", "whisper").strip() or "whisper"
    model = os.environ.get("GYTE_WHISPER_MODEL", "base").strip() or "base"
    whisper = _resolve_executable(command, "Whisper")

    output_dir = workdir / WHISPER_OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [
            whisper,
            str(audio_path),
            "--model",
            model,
            "--output_dir",
            str(output_dir),
            "--output_format",
            "txt",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    detail = completed.stderr.strip() or completed.stdout.strip()
    if completed.returncode != 0:
        raise LocalTranscriptionError(
            "transcription",
            "Whisper non ha completato la trascrizione locale."
            + (f" Dettaglio: {detail}" if detail else ""),
        )

    generated = output_dir / f"{audio_path.stem}.txt"
    if not _is_usable_regular_file(generated):
        candidates = [
            path
            for path in output_dir.glob("*.txt")
            if _is_usable_regular_file(path)
        ]
        generated = max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else generated

    if not _is_usable_regular_file(generated):
        raise LocalTranscriptionError(
            "output",
            "Whisper è terminato senza produrre un transcript locale utilizzabile.",
        )

    try:
        text = generated.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LocalTranscriptionError(
            "output",
            f"Transcript Whisper illeggibile: {generated}",
        ) from error

    if not text.strip():
        raise LocalTranscriptionError(
            "output",
            "Il transcript Whisper è vuoto.",
        )

    stable = workdir / LOCAL_TRANSCRIPT_FILENAME
    _atomic_write_text(stable, text)
    return stable, model


def transcribe_locally(
    url: str,
    workdir: Path,
    force: bool = False,
) -> LocalTranscriptionResult:
    """Return a stable private local transcript, reusing safe completed work."""
    workdir = workdir.expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    stable = workdir / LOCAL_TRANSCRIPT_FILENAME
    if not force and _is_usable_regular_file(stable):
        audio = locate_local_audio(workdir)
        if audio is None:
            raise LocalTranscriptionError(
                "output",
                "Transcript locale esistente senza il relativo audio privato di provenance.",
            )
        model = os.environ.get("GYTE_WHISPER_MODEL", "base").strip() or "base"
        return LocalTranscriptionResult(
            transcript_path=stable,
            audio_path=audio,
            reused_transcript=True,
            reused_audio=True,
            model=model,
        )

    audio, reused_audio = acquire_audio(url, workdir)
    transcript, model = transcribe_audio(audio, workdir)
    return LocalTranscriptionResult(
        transcript_path=transcript,
        audio_path=audio,
        reused_transcript=False,
        reused_audio=reused_audio,
        model=model,
    )
