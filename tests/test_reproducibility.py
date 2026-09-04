"""Tests for publication reproducibility semantics."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from gyte_study_tools.reproducibility import (  # noqa: E402
    build_report,
    compare_reports,
)


class ReproducibilityTests(unittest.TestCase):
    def sha(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def make_publication(
        self,
        root: Path,
        *,
        pdf_bytes: bytes,
        epub_marker: str,
        reviewed_hash: str | None = None,
    ) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        markdown = root / "Lesson.md"
        html = root / "Lesson.html"
        pdf = root / "Lesson.pdf"
        epub = root / "Lesson.epub"

        markdown.write_text("# Lesson\n\nSame semantic content.\n", encoding="utf-8")
        html.write_text(
            "<!doctype html><html><body><h1>Lesson</h1>"
            "<p>Same semantic content.</p></body></html>\n",
            encoding="utf-8",
        )
        pdf.write_bytes(pdf_bytes)
        with zipfile.ZipFile(epub, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr(
                "content.xhtml",
                "<html><body><h1>Lesson</h1><p>Same semantic content.</p>"
                f"<!-- {epub_marker} --></body></html>",
            )

        markdown_hash = self.sha(markdown)
        manifest = {
            "schema_version": 2,
            "reviewed_source": {
                "role": "reviewed-source-snapshot",
                "sha256": reviewed_hash or markdown_hash,
                "copied_to": "markdown",
                "h1": "Lesson",
            },
            "files": {
                "markdown": {"path": markdown.name, "sha256": markdown_hash},
                "html": {"path": html.name, "sha256": self.sha(html)},
                "pdf": {"path": pdf.name, "sha256": self.sha(pdf)},
                "epub": {"path": epub.name, "sha256": self.sha(epub)},
            },
        }
        manifest_path = root / "publication-manifest.json"
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        return manifest_path

    def test_byte_variation_is_allowed_for_content_reproducible_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_manifest = self.make_publication(
                root / "left",
                pdf_bytes=b"pdf metadata A",
                epub_marker="metadata A",
            )
            right_manifest = self.make_publication(
                root / "right",
                pdf_bytes=b"pdf metadata B",
                epub_marker="metadata B",
            )

            with patch(
                "gyte_study_tools.reproducibility.pdf_visible_text",
                return_value="Lesson\nSame semantic content.\n",
            ):
                left = build_report(left_manifest)
                right = build_report(right_manifest)

            comparison = compare_reports(left, right)
            self.assertTrue(comparison["equivalent_input"])
            self.assertTrue(comparison["reproducible"])
            self.assertTrue(comparison["formats"]["markdown"]["byte_identical"])
            self.assertTrue(comparison["formats"]["html"]["byte_identical"])
            self.assertFalse(comparison["formats"]["pdf"]["byte_identical"])
            self.assertFalse(comparison["formats"]["epub"]["byte_identical"])
            self.assertEqual(
                comparison["formats"]["pdf"]["compared_identity"],
                "normalized_sha256",
            )

    def test_pdf_content_change_breaks_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_manifest = self.make_publication(
                root / "left",
                pdf_bytes=b"pdf A",
                epub_marker="same",
            )
            right_manifest = self.make_publication(
                root / "right",
                pdf_bytes=b"pdf B",
                epub_marker="same",
            )

            with patch(
                "gyte_study_tools.reproducibility.pdf_visible_text",
                side_effect=[
                    "Lesson\nSame semantic content.\n",
                    "Lesson\nDifferent semantic content.\n",
                ],
            ):
                left = build_report(left_manifest)
                right = build_report(right_manifest)

            comparison = compare_reports(left, right)
            self.assertFalse(comparison["reproducible"])
            self.assertFalse(comparison["formats"]["pdf"]["match"])

    def test_different_reviewed_input_is_not_comparable_as_same_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_manifest = self.make_publication(
                root / "left",
                pdf_bytes=b"pdf A",
                epub_marker="same",
            )
            right_manifest = self.make_publication(
                root / "right",
                pdf_bytes=b"pdf A",
                epub_marker="same",
            )
            right_data = json.loads(right_manifest.read_text(encoding="utf-8"))
            right_data["reviewed_source"]["sha256"] = "f" * 64
            right_manifest.write_text(json.dumps(right_data) + "\n", encoding="utf-8")

            with patch(
                "gyte_study_tools.reproducibility.pdf_visible_text",
                return_value="Lesson\nSame semantic content.\n",
            ):
                left = build_report(left_manifest)
                # The report itself rejects a reviewed-source snapshot that does
                # not match the current Markdown bytes, so compare cannot silently
                # treat a different input as equivalent.
                with self.assertRaises(Exception):
                    build_report(right_manifest)


if __name__ == "__main__":
    unittest.main()
