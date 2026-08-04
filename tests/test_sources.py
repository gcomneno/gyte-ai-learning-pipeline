"""Tests for source detection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gyte_study_tools.sources import (  # noqa: E402
    SourceDetectionError,
    detect_source_type,
)


class SourceDetectionTests(unittest.TestCase):
    def test_youtube_urls_are_detected(self) -> None:
        self.assertEqual(
            detect_source_type(
                "https://www.youtube.com/watch?v=example"
            ),
            "youtube",
        )
        self.assertEqual(
            detect_source_type("https://youtu.be/example"),
            "youtube",
        )

    def test_article_url_is_detected(self) -> None:
        self.assertEqual(
            detect_source_type(
                "https://news.example.test/article.html"
            ),
            "article",
        )

    def test_invalid_url_is_rejected(self) -> None:
        with self.assertRaises(SourceDetectionError):
            detect_source_type("not-a-url")


if __name__ == "__main__":
    unittest.main()
