"""Tests for source-lesson publication."""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC))

from gyte_study_tools.publishing import (  # noqa: E402
    ConversionMetrics,
    PublicationError,
    extract_heading,
    normalize_publication_title,
    publish_lesson,
    render_document,
    validate_publication_manifest,
)


class PublishingTests(unittest.TestCase):
    def write_epub(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("content.txt", "EPUB fixture senza rete")

    def fake_conversion(
        self,
        html_path: Path,
        pdf_path: Path,
        epub_path: Path,
        title: str,
        author: str,
        source_words: int,
        temporary_directory: Path,
    ) -> ConversionMetrics:
        pdf_path.write_bytes(b"%PDF-fake")
        self.write_epub(epub_path)

        return ConversionMetrics(
            source_words=source_words,
            pdf_words=source_words,
            epub_words=source_words,
        )

    def make_publish_fixture(self, root: Path) -> tuple[Path, Path, bytes, bytes]:
        workdir = root / "workspace"
        workdir.mkdir()
        metadata = {
            "schema_version": 1,
            "source": {"requested_url": "https://www.youtube.com/watch?v=fixture"},
            "video": {"id": "fixture", "title": "Video fixture"},
        }
        metadata_bytes = json.dumps(metadata, ensure_ascii=False, indent=2).encode(
            "utf-8"
        ) + b"\n"
        (workdir / "metadata.json").write_bytes(metadata_bytes)
        analysis_bytes = b"# Analisi preparata\n\nContesto osservato.\n"
        (workdir / "transcript.analysis.md").write_bytes(analysis_bytes)
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "video_id": "fixture",
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
        source.write_bytes(
            b"# Titolo di prova\n\nQuesto e il contenuto della lezione.\n"
        )
        return workdir, source, metadata_bytes, analysis_bytes

    def publish_fixture(self, root: Path, output_dir: Path | None = None):
        workdir, source, metadata_bytes, analysis_bytes = self.make_publish_fixture(root)
        with patch(
            "gyte_study_tools.publishing.build_converted_outputs",
            side_effect=self.fake_conversion,
        ):
            result = publish_lesson(workdir, source, output_dir=output_dir)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        return workdir, source, metadata_bytes, analysis_bytes, result, manifest

    def test_title_is_preserved_for_publication(self) -> None:
        self.assertEqual(
            normalize_publication_title(
                "Lesson Learned — Salvare il salvabile"
            ),
            "Lesson Learned — Salvare il salvabile",
        )

    def test_markdown_is_rendered_semantically(self) -> None:
        markdown = """
# Prova

## Sezione

Testo con **grassetto** e ``codice``.

> Una citazione.

- primo
- secondo
"""

        document = render_document(
            markdown,
            "Prova",
            "Autore",
        )

        self.assertIn("<h1>", document)
        self.assertIn("<h2>", document)
        self.assertIn("<strong>grassetto</strong>", document)
        self.assertIn("<code>codice</code>", document)
        self.assertIn("<blockquote>", document)
        self.assertIn("<ul>", document)

    def test_publish_writes_manifest_v2_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                workdir,
                source,
                metadata_bytes,
                analysis_bytes,
                result,
                manifest,
            ) = self.publish_fixture(root)

            self.assertTrue(result.markdown_path.is_file())
            self.assertTrue(result.html_path.is_file())
            self.assertTrue(result.pdf_path.is_file())
            self.assertTrue(result.epub_path.is_file())
            self.assertTrue(result.manifest_path.is_file())
            self.assertEqual(
                result.title,
                "Titolo di prova",
            )
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(
                manifest["title"],
                "Titolo di prova",
            )
            self.assertEqual(
                manifest["source_context"]["relationship"],
                "observed-at-publication-time",
            )
            self.assertEqual(manifest["source_context"]["source_type"], "youtube")
            self.assertEqual(
                manifest["source_context"]["source_id_kind"],
                "youtube-video-id",
            )
            self.assertEqual(manifest["source_context"]["source_id"], "fixture")
            self.assertEqual(
                manifest["source_context"]["metadata_sha256"],
                hashlib.sha256(metadata_bytes).hexdigest(),
            )
            self.assertEqual(
                manifest["source_context"]["prepared_artifacts"],
                [
                    {
                        "role": "prepared-analysis",
                        "name": "transcript.analysis.md",
                        "sha256": hashlib.sha256(analysis_bytes).hexdigest(),
                    }
                ],
            )
            self.assertEqual(
                manifest["reviewed_source"]["role"],
                "reviewed-source-snapshot",
            )
            self.assertEqual(manifest["reviewed_source"]["copied_to"], "markdown")
            self.assertEqual(manifest["reviewed_source"]["h1"], "Titolo di prova")
            self.assertEqual(
                manifest["reviewed_source"]["sha256"],
                manifest["files"]["markdown"]["sha256"],
            )
            self.assertEqual(
                manifest["files"]["markdown"]["role"],
                "reviewed-source-copy",
            )
            self.assertEqual(
                manifest["files"]["html"]["role"],
                "derived-publication-html",
            )
            self.assertEqual(manifest["files"]["html"]["derived_from"], "markdown")
            self.assertEqual(
                manifest["files"]["pdf"]["role"],
                "derived-publication-pdf",
            )
            self.assertEqual(manifest["files"]["pdf"]["derived_from"], "html")
            self.assertEqual(
                manifest["files"]["epub"]["role"],
                "derived-publication-epub",
            )
            self.assertEqual(manifest["files"]["epub"]["derived_from"], "html")
            self.assertNotIn(str(source), json.dumps(manifest, ensure_ascii=False))
            for record in manifest["files"].values():
                self.assertFalse(Path(record["path"]).is_absolute())
            validate_publication_manifest(
                result.manifest_path,
                workdir=workdir,
                expected_epub_path=result.epub_path,
            )
            self.assertEqual(
                state["stages"]["publish"]["status"],
                "complete",
            )
            self.assertEqual(
                state["stages"]["publish"]["outputs"]["markdown"],
                str(result.markdown_path),
            )

    def test_publish_supports_external_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "external-publication"
            workdir, _, _, _, result, _ = self.publish_fixture(
                root,
                output_dir=output_dir,
            )

            self.assertEqual(result.manifest_path.parent, output_dir.resolve())
            self.assertTrue(result.epub_path.is_file())
            validate_publication_manifest(
                result.manifest_path,
                workdir=workdir,
                expected_epub_path=result.epub_path,
            )
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                state["stages"]["publish"]["outputs"]["manifest"],
                str(result.manifest_path),
            )
            self.assertEqual(
                state["stages"]["publish"]["outputs"]["epub"],
                str(result.epub_path),
            )

    def test_publish_requires_exactly_one_h1(self) -> None:
        with self.assertRaisesRegex(PublicationError, "esattamente un"):
            extract_heading("# Primo\n\n# Secondo\n")

    def test_manifest_validator_rejects_malformed_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, manifest = self.publish_fixture(root)
            manifest["files"]["html"]["sha256"] = "not-a-sha"
            result.manifest_path.write_text(
                json.dumps(manifest) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )

    def test_manifest_validator_rejects_unsafe_prepared_artifact_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, manifest = self.publish_fixture(root)

            for unsafe_name in ("../transcript.analysis.md", str(root / "secret.md")):
                with self.subTest(unsafe_name=unsafe_name):
                    mutated = json.loads(json.dumps(manifest))
                    mutated["source_context"]["prepared_artifacts"][0][
                        "name"
                    ] = unsafe_name
                    result.manifest_path.write_text(
                        json.dumps(mutated) + "\n",
                        encoding="utf-8",
                    )

                    with self.assertRaises(PublicationError):
                        validate_publication_manifest(
                            result.manifest_path,
                            workdir=workdir,
                            expected_epub_path=result.epub_path,
                        )

    def test_manifest_validator_rejects_unsafe_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, manifest = self.publish_fixture(root)

            for unsafe_path in ("../lesson.md", str(root / "outside.md")):
                with self.subTest(unsafe_path=unsafe_path):
                    mutated = json.loads(json.dumps(manifest))
                    mutated["files"]["markdown"]["path"] = unsafe_path
                    result.manifest_path.write_text(
                        json.dumps(mutated) + "\n",
                        encoding="utf-8",
                    )

                    with self.assertRaises(PublicationError):
                        validate_publication_manifest(
                            result.manifest_path,
                            workdir=workdir,
                            expected_epub_path=result.epub_path,
                        )

    def test_manifest_validator_rejects_modified_metadata_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, _ = self.publish_fixture(root)
            (workdir / "metadata.json").write_bytes(
                b'{"schema_version": 1, "video": {"id": "changed"}}\n'
            )

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )

    def test_manifest_validator_rejects_missing_metadata_json_when_claimed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, _ = self.publish_fixture(root)
            (workdir / "metadata.json").unlink()

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )

    def test_manifest_validator_rejects_tampered_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, _ = self.publish_fixture(root)
            result.markdown_path.write_text(
                "# Titolo di prova\n\nContenuto manomesso.\n",
                encoding="utf-8",
            )

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )

    def test_manifest_validator_rejects_tampered_epub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, _ = self.publish_fixture(root)
            result.epub_path.write_bytes(b"EPUB manomesso")

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )

    def test_manifest_validator_rejects_reviewed_source_markdown_mismatch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, _, _, _, result, manifest = self.publish_fixture(root)
            manifest["reviewed_source"]["sha256"] = "0" * 64
            result.manifest_path.write_text(
                json.dumps(manifest) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(PublicationError):
                validate_publication_manifest(
                    result.manifest_path,
                    workdir=workdir,
                    expected_epub_path=result.epub_path,
                )


if __name__ == "__main__":
    unittest.main()
