"""Tests for transcript preparation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
FIXTURE = PROJECT_ROOT / "tests/fixtures/youtube-metadata.json"

sys.path.insert(0, str(SRC))

from gyte_study_tools.inspection import inspect_video  # noqa: E402
from gyte_study_tools.preparation import (  # noqa: E402
    PreparationError,
    count_words,
    lexical_word_tokens,
    locate_caption_transcript,
    prepare_transcript,
    run_gyte_transcript,
)
from gyte_study_tools.transcription import LocalTranscriptionError  # noqa: E402


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def make_workspace(self, root: Path) -> Path:
        url = "https://www.youtube.com/watch?v=bWPJ-hn9Xrw"

        with patch(
            "gyte_study_tools.inspection.fetch_metadata",
            return_value=self.metadata,
        ):
            result = inspect_video(url, root)

        return result.workdir

    def test_prepare_uses_existing_caption_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            source = workdir / "video.it-orig.txt"
            source.write_text(
                "Ciao &amp; benvenuti.\nSeconda frase.\n",
                encoding="utf-8",
            )

            def fake_reflow(
                input_path: Path,
                output_path: Path,
            ) -> None:
                output_path.write_text(
                    input_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                result = prepare_transcript(workdir)

            self.assertFalse(result.reused)
            self.assertEqual(result.source_mode, "existing-caption")
            self.assertEqual(result.normalized_words, result.analysis_words)
            self.assertIn(
                "Ciao & benvenuti.",
                result.normalized_path.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "## Transcript riorganizzato",
                result.analysis_markdown_path.read_text(encoding="utf-8"),
            )

            state = json.loads(
                (workdir / "pipeline-state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                state["stages"]["prepare"]["status"],
                "complete",
            )

    def test_prepare_reuses_complete_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            source = workdir / "video.it-orig.txt"
            source.write_text(
                "Prima frase.\nSeconda frase.\n",
                encoding="utf-8",
            )

            def fake_reflow(
                input_path: Path,
                output_path: Path,
            ) -> None:
                output_path.write_text(
                    input_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                prepare_transcript(workdir)

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=AssertionError(
                    "Il reflow non deve essere rieseguito."
                ),
            ):
                reused = prepare_transcript(workdir)

            self.assertTrue(reused.reused)
            self.assertEqual(
                reused.source_mode,
                "existing-caption",
            )

    def test_prepare_accepts_punctuation_attached_by_reflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            source = workdir / "video.it-orig.txt"
            source.write_text(
                "cose buone , la gente\n",
                encoding="utf-8",
            )

            def fake_reflow(
                input_path: Path,
                output_path: Path,
            ) -> None:
                self.assertEqual(
                    input_path.read_text(encoding="utf-8"),
                    "cose buone , la gente\n",
                )
                output_path.write_text(
                    "cose buone, la gente\n",
                    encoding="utf-8",
                )

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                result = prepare_transcript(workdir)

            self.assertEqual(result.normalized_words, 4)
            self.assertEqual(result.analysis_words, 4)

    def test_prepare_rejects_lexical_removal_by_reflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            source = workdir / "video.it-orig.txt"
            source.write_text(
                "cose buone, la gente\n",
                encoding="utf-8",
            )

            def fake_reflow(_: Path, output_path: Path) -> None:
                output_path.write_text(
                    "cose buone, gente\n",
                    encoding="utf-8",
                )

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                with self.assertRaisesRegex(
                    PreparationError,
                    "sequenza lessicale",
                ):
                    prepare_transcript(workdir)

    def test_prepare_rejects_equal_count_lexical_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            source = workdir / "video.it-orig.txt"
            source.write_text(
                "cose buone, la gente\n",
                encoding="utf-8",
            )

            def fake_reflow(_: Path, output_path: Path) -> None:
                output_path.write_text(
                    "cose belle, la gente\n",
                    encoding="utf-8",
                )

            with patch(
                "gyte_study_tools.preparation.run_reflow",
                side_effect=fake_reflow,
            ):
                with self.assertRaisesRegex(
                    PreparationError,
                    "sequenza lessicale",
                ):
                    prepare_transcript(workdir)

    def test_lexical_word_tokens_canonicalize_internal_apostrophes(
        self,
    ) -> None:
        self.assertEqual(
            lexical_word_tokens("l'anno, l’anno"),
            ("l'anno", "l'anno"),
        )
        self.assertEqual(count_words("l'anno, l’anno"), 2)

    def test_original_caption_reuses_base_language_transcript(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            source = workdir / "video.en.txt"
            source.write_text(
                "Existing English source transcript.\n",
                encoding="utf-8",
            )

            located = locate_caption_transcript(
                workdir,
                "en-orig",
            )

            self.assertEqual(located, source)

    def test_transcript_success_without_output_preserves_diagnostic(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)

            completed = subprocess.CompletedProcess(
                args=["gyte-transcript"],
                returncode=0,
                stdout="",
                stderr="download non riuscito: HTTP 429",
            )

            with (
                patch(
                    "gyte_study_tools.preparation.shutil.which",
                    return_value="/usr/bin/gyte-transcript",
                ),
                patch(
                    "gyte_study_tools.preparation.subprocess.run",
                    return_value=completed,
                ),
            ):
                with self.assertRaisesRegex(
                    PreparationError,
                    "HTTP 429",
                ):
                    run_gyte_transcript(
                        "https://www.youtube.com/watch?v=fixture",
                        workdir,
                        "it",
                    )

    def test_prepare_uses_local_fallback_when_caption_is_missing(self) -> None:
        metadata = dict(self.metadata)
        metadata["subtitles"] = {}
        metadata["automatic_captions"] = {}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            url = "https://www.youtube.com/watch?v=bWPJ-hn9Xrw"

            with patch(
                "gyte_study_tools.inspection.fetch_metadata",
                return_value=metadata,
            ):
                result = inspect_video(url, root)

            with patch(
                "gyte_study_tools.preparation.transcribe_locally",
                side_effect=LocalTranscriptionError(
                    "configuration",
                    "Whisper non disponibile",
                ),
            ):
                with self.assertRaisesRegex(
                    PreparationError,
                    "Fallback di trascrizione locale fallito \(configuration\)",
                ):
                    prepare_transcript(result.workdir)

            state = json.loads(
                (result.workdir / "pipeline-state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("transcribe", state["stages"])
            self.assertNotIn("prepare", state["stages"])


if __name__ == "__main__":
    unittest.main()
