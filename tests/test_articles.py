"""Tests for article ingestion."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
FIXTURE = PROJECT_ROOT / "tests/fixtures/article.html"

sys.path.insert(0, str(SRC))

from gyte_study_tools.articles import ingest_article  # noqa: E402


class ArticleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = FIXTURE.read_text(encoding="utf-8")
        cls.url = "https://example.test/article.html"

    def test_article_is_extracted_without_page_boilerplate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "gyte_study_tools.articles.fetch_article",
                return_value=self.document,
            ):
                result = ingest_article(
                    self.url,
                    Path(temporary),
                )

            self.assertFalse(result.reused)
            self.assertGreater(result.content_words, 50)
            self.assertEqual(
                result.record["article"]["author"],
                "Team Example",
            )
            self.assertEqual(
                len(result.record["scientific_references"]),
                1,
            )

            analysis = result.analysis_markdown_path.read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "## Contenuto estratto",
                analysis,
            )
            self.assertIn(
                "## Riferimenti scientifici dichiarati",
                analysis,
            )
            self.assertNotIn("Popular Posts", analysis)
            self.assertNotIn("Post a Comment", analysis)

    def test_complete_article_outputs_are_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            with patch(
                "gyte_study_tools.articles.fetch_article",
                return_value=self.document,
            ):
                first = ingest_article(self.url, root)

            marker = "\nMARKER-PRESERVED\n"
            first.analysis_markdown_path.write_text(
                first.analysis_markdown_path.read_text(
                    encoding="utf-8"
                )
                + marker,
                encoding="utf-8",
            )

            with patch(
                "gyte_study_tools.articles.fetch_article",
                return_value=self.document,
            ):
                reused = ingest_article(self.url, root)

            self.assertTrue(reused.reused)
            self.assertIn(
                "MARKER-PRESERVED",
                reused.analysis_markdown_path.read_text(
                    encoding="utf-8"
                ),
            )

    def test_inspect_only_does_not_write_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "gyte_study_tools.articles.fetch_article",
                return_value=self.document,
            ):
                result = ingest_article(
                    self.url,
                    Path(temporary),
                    inspect_only=True,
                )

            self.assertIsNone(result.analysis_markdown_path)
            self.assertIsNone(result.extracted_markdown_path)
            self.assertTrue(result.metadata_path.is_file())
            self.assertTrue(result.raw_html_path.is_file())

            state = json.loads(
                result.state_path.read_text(encoding="utf-8")
            )
            self.assertNotIn("prepare", state["stages"])


if __name__ == "__main__":
    unittest.main()
