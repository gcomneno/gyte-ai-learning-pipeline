"""Integration-style tests for preparation selecting local transcription fallback."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from gyte_study_tools.preparation import PreparationError, prepare_transcript  # noqa: E402
from gyte_study_tools.transcription import (  # noqa: E402
    LocalTranscriptionError,
    LocalTranscriptionResult,
)


class PreparationLocalFallbackTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> Path:
        workdir = root / "workspace"
        workdir.mkdir()
        metadata = {
            "schema_version": 1,
            "source": {
                "requested_url": "https://www.youtube.com/watch?v=no-captions",
                "webpage_url": "https://www.youtube.com/watch?v=no-captions",
            },
            "video": {
                "id": "no-captions",
                "title": "Video senza caption",
                "channel": "Fixture",
            },
            "captions": {
                "selected": None,
                "manual": {},
                "automatic": {},
            },
        }
        (workdir / "metadata.json").write_text(
            json.dumps(metadata) + "\n",
            encoding="utf-8",
        )
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "video_id": "no-captions",
                    "stages": {"inspect": {"status": "complete"}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workdir

    def test_no_caption_selects_local_transcription_and_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir = self.make_workspace(root)
            audio = workdir / "transcription-source.webm"
            audio.write_bytes(b"audio")
            local = workdir / "transcription.local.txt"
            local.write_text("Uno due tre.\n", encoding="utf-8")

            def fake_reflow(source: Path, destination: Path) -> None:
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            with patch(
                "gyte_study_tools.preparation.transcribe_locally",
                return_value=LocalTranscriptionResult(
                    transcript_path=local,
                    audio_path=audio,
                    reused_transcript=False,
                    reused_audio=True,
                    model="tiny",
                ),
            ), patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                result = prepare_transcript(workdir)

            self.assertEqual(result.source_mode, "generated-local-transcription")
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )
            transcribe = state["stages"]["transcribe"]
            self.assertEqual(transcribe["status"], "complete")
            self.assertEqual(transcribe["evidence_origin"], "local-transcription")
            self.assertEqual(
                transcribe["local_transcription"]["audio"],
                "transcription-source.webm",
            )
            self.assertEqual(transcribe["local_transcription"]["model"], "tiny")
            self.assertEqual(state["stages"]["prepare"]["status"], "complete")
            self.assertIn(
                "Fonte testuale: trascrizione locale",
                result.analysis_markdown_path.read_text(encoding="utf-8"),
            )

    def test_fallback_failure_does_not_advance_prepare_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))

            with patch(
                "gyte_study_tools.preparation.transcribe_locally",
                side_effect=LocalTranscriptionError(
                    "configuration",
                    "Whisper assente",
                ),
            ):
                with self.assertRaises(PreparationError) as raised:
                    prepare_transcript(workdir)

            self.assertIn("configuration", str(raised.exception))
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["stages"]["inspect"]["status"], "complete")
            self.assertNotIn("prepare", state["stages"])
            self.assertNotIn("transcribe", state["stages"])


if __name__ == "__main__":
    unittest.main()
