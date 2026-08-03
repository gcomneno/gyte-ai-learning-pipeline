"""Tests for Lesson Learned publication."""

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

from gyte_study_tools.publishing import (  # noqa: E402
    ConversionMetrics,
    normalize_publication_title,
    publish_lesson,
    render_document,
)


class PublishingTests(unittest.TestCase):
    def test_title_is_reordered_for_kindle(self) -> None:
        self.assertEqual(
            normalize_publication_title(
                "Lesson Learned — Salvare il salvabile"
            ),
            "Salvare il salvabile — Lesson Learned",
        )

    def test_markdown_is_rendered_semantically(self) -> None:
        markdown = """
# Lesson Learned — Prova

## Sezione

Testo con **grassetto** e ``codice``.

> Una citazione.

- primo
- secondo
"""

        document = render_document(
            markdown,
            "Prova — Lesson Learned",
            "Autore",
        )

        self.assertIn("<h1>", document)
        self.assertIn("<h2>", document)
        self.assertIn("<strong>grassetto</strong>", document)
        self.assertIn("<code>codice</code>", document)
        self.assertIn("<blockquote>", document)
        self.assertIn("<ul>", document)

    def test_publish_writes_manifest_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir = root / "workspace"
            workdir.mkdir()

            (workdir / "pipeline-state.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stages": {
                            "inspect": {"status": "complete"},
                            "prepare": {"status": "complete"},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            source = root / "lesson.md"
            source.write_text(
                "# Lesson Learned — Titolo di prova\n\n"
                "Questo è il contenuto della lezione.\n",
                encoding="utf-8",
            )

            def fake_conversion(
                html_path: Path,
                pdf_path: Path,
                epub_path: Path,
                title: str,
                author: str,
                source_words: int,
                temporary_directory: Path,
            ) -> ConversionMetrics:
                pdf_path.write_bytes(b"%PDF-fake")
                epub_path.write_bytes(b"EPUB-fake")

                return ConversionMetrics(
                    source_words=source_words,
                    pdf_words=source_words,
                    epub_words=source_words,
                )

            with patch(
                "gyte_study_tools.publishing.build_converted_outputs",
                side_effect=fake_conversion,
            ):
                result = publish_lesson(workdir, source)

            self.assertTrue(result.canonical_markdown_path.is_file())
            self.assertTrue(result.html_path.is_file())
            self.assertTrue(result.pdf_path.is_file())
            self.assertTrue(result.epub_path.is_file())
            self.assertTrue(result.manifest_path.is_file())
            self.assertEqual(
                result.title,
                "Titolo di prova — Lesson Learned",
            )

            manifest = json.loads(
                result.manifest_path.read_text(encoding="utf-8")
            )
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["title"],
                "Titolo di prova — Lesson Learned",
            )
            self.assertEqual(
                state["stages"]["publish"]["status"],
                "complete",
            )


if __name__ == "__main__":
    unittest.main()
