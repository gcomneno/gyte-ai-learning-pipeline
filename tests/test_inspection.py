"""Tests for YouTube inspection and workspace preparation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
FIXTURE = PROJECT_ROOT / "tests/fixtures/youtube-metadata.json"

sys.path.insert(0, str(SRC))

from gyte_study_tools.inspection import (  # noqa: E402
    choose_caption,
    inspect_video,
    normalize_upload_date,
    slugify,
)


class InspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_slugify_normalizes_title(self) -> None:
        self.assertEqual(
            slugify("È già l'ora: Natura & Cultura!"),
            "e-gia-l-ora-natura-cultura",
        )

    def test_upload_date_is_normalized(self) -> None:
        self.assertEqual(
            normalize_upload_date("20251120"),
            "2025-11-20",
        )

    def test_original_automatic_caption_is_selected(self) -> None:
        selected = choose_caption(self.metadata)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.language, "it-orig")
        self.assertEqual(selected.source, "automatic")
        self.assertEqual(
            selected.formats,
            ("json3", "srt", "vtt"),
        )

    def test_original_language_beats_automatic_translation(self) -> None:
        metadata = {
            "subtitles": {},
            "automatic_captions": {
                "en": [{"ext": "vtt"}],
                "en-orig": [
                    {"ext": "vtt"},
                    {"ext": "json3"},
                ],
                "it": [{"ext": "vtt"}],
            },
        }

        selected = choose_caption(metadata)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.language, "en-orig")
        self.assertEqual(selected.source, "automatic")
        self.assertEqual(selected.formats, ("json3", "vtt"))

    def test_manual_original_language_beats_automatic_original(self) -> None:
        metadata = {
            "subtitles": {
                "en": [{"ext": "vtt"}],
            },
            "automatic_captions": {
                "en-orig": [{"ext": "vtt"}],
                "it": [{"ext": "vtt"}],
            },
        }

        selected = choose_caption(metadata)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.language, "en")
        self.assertEqual(selected.source, "manual")

    def test_inspect_video_writes_restartable_workspace(self) -> None:
        url = "https://www.youtube.com/watch?v=bWPJ-hn9Xrw"

        with tempfile.TemporaryDirectory() as temporary:
            work_root = Path(temporary)

            with patch(
                "gyte_study_tools.inspection.fetch_metadata",
                return_value=self.metadata,
            ):
                result = inspect_video(url, work_root)

            self.assertTrue(result.metadata_path.is_file())
            self.assertTrue(result.state_path.is_file())
            self.assertEqual(
                (result.workdir / "source-url.txt").read_text(
                    encoding="utf-8"
                ),
                url + "\n",
            )

            record = json.loads(
                result.metadata_path.read_text(encoding="utf-8")
            )
            state = json.loads(
                result.state_path.read_text(encoding="utf-8")
            )

            self.assertEqual(record["video"]["id"], "bWPJ-hn9Xrw")
            self.assertEqual(
                record["captions"]["selected"]["language"],
                "it-orig",
            )
            self.assertEqual(
                state["stages"]["inspect"]["status"],
                "complete",
            )


if __name__ == "__main__":
    unittest.main()
