"""Tests for the local-first transcription fallback."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from gyte_study_tools.transcription import (  # noqa: E402
    LocalTranscriptionError,
    transcribe_locally,
)


class LocalTranscriptionTests(unittest.TestCase):
    def test_downloads_audio_and_generates_stable_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)

            def fake_run(command, **kwargs):
                if command[0].endswith("yt-dlp"):
                    (workdir / "transcription-source.webm").write_bytes(b"audio")
                elif command[0].endswith("whisper"):
                    output_dir = Path(command[command.index("--output_dir") + 1])
                    output_dir.mkdir(parents=True, exist_ok=True)
                    (output_dir / "transcription-source.txt").write_text(
                        "Transcript locale verificabile.\n",
                        encoding="utf-8",
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch(
                "gyte_study_tools.transcription.shutil.which",
                side_effect=lambda name: f"/usr/bin/{name}",
            ), patch(
                "gyte_study_tools.transcription.subprocess.run",
                side_effect=fake_run,
            ) as run, patch.dict(
                os.environ,
                {"GYTE_WHISPER_MODEL": "tiny"},
                clear=False,
            ):
                result = transcribe_locally(
                    "https://www.youtube.com/watch?v=fixture",
                    workdir,
                )

            self.assertEqual(result.transcript_path.name, "transcription.local.txt")
            self.assertEqual(result.audio_path.name, "transcription-source.webm")
            self.assertFalse(result.reused_audio)
            self.assertFalse(result.reused_transcript)
            self.assertEqual(result.model, "tiny")
            self.assertEqual(run.call_count, 2)
            self.assertIn(
                "Transcript locale verificabile.",
                result.transcript_path.read_text(encoding="utf-8"),
            )

    def test_reuses_completed_private_audio_and_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "transcription-source.m4a").write_bytes(b"audio")
            transcript = workdir / "transcription.local.txt"
            transcript.write_text("Già completato.\n", encoding="utf-8")

            with patch("gyte_study_tools.transcription.subprocess.run") as run:
                result = transcribe_locally("https://example.invalid/video", workdir)

            run.assert_not_called()
            self.assertEqual(result.transcript_path, transcript)
            self.assertTrue(result.reused_audio)
            self.assertTrue(result.reused_transcript)

    def test_whisper_failure_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "transcription-source.webm").write_bytes(b"audio")

            with patch(
                "gyte_study_tools.transcription.shutil.which",
                return_value="/usr/bin/whisper",
            ), patch(
                "gyte_study_tools.transcription.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    ["whisper"],
                    2,
                    "",
                    "model failure",
                ),
            ):
                with self.assertRaises(LocalTranscriptionError) as raised:
                    transcribe_locally("https://example.invalid/video", workdir)

            self.assertEqual(raised.exception.kind, "transcription")
            self.assertIn("model failure", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
