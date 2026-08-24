"""Tests for the command-line interface."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC))

from gyte_study_tools import __version__  # noqa: E402
from gyte_study_tools.cli import REQUIRED_COMMANDS, build_parser, main  # noqa: E402
from gyte_study_tools.inspection import DEFAULT_WORK_ROOT  # noqa: E402
from gyte_study_tools.publishing import DEFAULT_AUTHOR  # noqa: E402


class CliTests(unittest.TestCase):

    def make_workspace(self, root: Path, url: str) -> Path:
        workdir = root / "workspace"
        workdir.mkdir()
        (workdir / "metadata.json").write_text(
            json.dumps({"schema_version": 1, "source": {"requested_url": url}})
            + "\n",
            encoding="utf-8",
        )
        return workdir

    def review_result(self, workdir: Path, source_type: str = "youtube") -> SimpleNamespace:
        source_id_kind = (
            "article-source-id" if source_type == "article" else "youtube-video-id"
        )
        source_id = "article-fixture" if source_type == "article" else "fixture"
        return SimpleNamespace(
            workdir=workdir,
            checkpoint_path=workdir / "reviewed-source-checkpoint.json",
            checkpoint_sha256="1" * 64,
            checkpoint={
                "checkpoint_id": "review-" + "2" * 64,
                "source_identity": {
                    "source_type": source_type,
                    "source_id_kind": source_id_kind,
                    "source_id": source_id,
                },
            },
        )

    def publication_result(self, workdir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            title="Fixture",
            author=DEFAULT_AUTHOR,
            markdown_path=workdir / "publication" / "Fixture.md",
            html_path=workdir / "publication" / "Fixture.html",
            pdf_path=workdir / "publication" / "Fixture.pdf",
            epub_path=workdir / "publication" / "Fixture.epub",
            manifest_path=workdir / "publication" / "publication-manifest.json",
            metrics=SimpleNamespace(source_words=1, pdf_words=1, epub_words=1),
            backups={},
        )

    def inspection_result(self, workdir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            workdir=workdir,
            metadata_path=workdir / "metadata.json",
            state_path=workdir / "pipeline-state.json",
            record={},
        )

    def preparation_result(self, workdir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            workdir=workdir,
            analysis_markdown_path=workdir / "transcript.analysis.md",
            raw_words=1,
            normalized_words=1,
            analysis_words=1,
            source_mode="fixture",
            reused=False,
        )

    def article_result(self, workdir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            workdir=workdir,
            metadata_path=workdir / "metadata.json",
            state_path=workdir / "pipeline-state.json",
            raw_html_path=workdir / "article.raw.html",
            extracted_markdown_path=workdir / "article.extracted.md",
            analysis_markdown_path=workdir / "article.analysis.md",
            content_words=1,
            reused=False,
            record={},
        )
    def test_development_version_is_exposed(self) -> None:
        self.assertEqual(__version__, "0.5.0-dev")

    def test_check_option_is_parsed(self) -> None:
        args = build_parser().parse_args(["--check"])

        self.assertTrue(args.check)
        self.assertIsNone(args.url)

    def test_video_url_is_parsed(self) -> None:
        url = "https://www.youtube.com/watch?v=example"
        args = build_parser().parse_args([url])

        self.assertEqual(args.url, url)
        self.assertFalse(args.check)
        self.assertFalse(args.inspect_only)
        self.assertFalse(args.force)
        self.assertIsNone(args.publish_from)
        self.assertEqual(args.author, DEFAULT_AUTHOR)
        self.assertEqual(args.work_root, DEFAULT_WORK_ROOT)

    def test_publish_options_are_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--publish-from",
                "/tmp/lesson.md",
                "--output-dir",
                "/tmp/publication",
                "--author",
                "Autore di prova",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertEqual(args.publish_from, Path("/tmp/lesson.md"))
        self.assertEqual(args.output_dir, Path("/tmp/publication"))
        self.assertEqual(args.author, "Autore di prova")

    def test_publish_help_uses_source_lesson_terminology(self) -> None:
        help_text = build_parser().format_help()

        self.assertIn("lezione sorgente", help_text)
        self.assertNotIn("Lesson Learned", help_text)

    def test_kindle_delivery_options_are_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--publish-from",
                "/tmp/lesson.md",
                "--kindle-email",
                "reader@kindle.com",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertEqual(args.kindle_email, "reader@kindle.com")
        self.assertIsNone(args.record_kindle_delivery)

    def test_output_dir_and_kindle_delivery_are_parsed_together(self) -> None:
        args = build_parser().parse_args(
            [
                "--publish-from",
                "/tmp/lesson.md",
                "--output-dir",
                "/tmp/publication",
                "--kindle-email",
                "reader@kindle.com",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertEqual(args.output_dir, Path("/tmp/publication"))
        self.assertEqual(args.kindle_email, "reader@kindle.com")

    def test_record_delivery_option_is_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--record-kindle-delivery",
                "gmail-message-123",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertEqual(args.record_kindle_delivery, "gmail-message-123")

    def test_kindle_email_requires_publish_from(self) -> None:
        with self.assertRaises(SystemExit):
            main(
                [
                    "--kindle-email",
                    "reader@kindle.com",
                    "https://www.youtube.com/watch?v=example",
                ]
            )

    def test_record_delivery_rejects_publish_options(self) -> None:
        with self.assertRaises(SystemExit):
            main(
                [
                    "--record-kindle-delivery",
                    "gmail-message-123",
                    "--publish-from",
                    "/tmp/lesson.md",
                    "https://www.youtube.com/watch?v=example",
                ]
            )

    def test_inspect_only_is_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--inspect-only",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertTrue(args.inspect_only)

    def test_force_is_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--force",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertTrue(args.force)

    def test_custom_work_root_is_parsed(self) -> None:
        args = build_parser().parse_args(
            ["--work-root", "/tmp/gyte-study", "https://youtu.be/example"]
        )

        self.assertEqual(args.work_root, Path("/tmp/gyte-study"))

    def test_expected_external_commands_are_declared(self) -> None:
        self.assertIn("gyte-transcript", REQUIRED_COMMANDS)
        self.assertIn("gyte-reflow-text", REQUIRED_COMMANDS)
        self.assertIn("yt-dlp", REQUIRED_COMMANDS)
        self.assertIn("ebook-convert", REQUIRED_COMMANDS)
        self.assertIn("pdftotext", REQUIRED_COMMANDS)


    def test_review_from_requires_url(self) -> None:
        with self.assertRaises(SystemExit) as context:
            main(
                [
                    "--review-from",
                    "/tmp/lesson.md",
                ]
            )

        self.assertEqual(context.exception.code, 2)

    def test_review_option_is_parsed(self) -> None:
        args = build_parser().parse_args(
            [
                "--review-from",
                "/tmp/lesson.md",
                "https://www.youtube.com/watch?v=example",
            ]
        )

        self.assertEqual(args.review_from, Path("/tmp/lesson.md"))
        self.assertEqual(args.url, "https://www.youtube.com/watch?v=example")

    def test_review_from_rejects_incompatible_options(self) -> None:
        url = "https://www.youtube.com/watch?v=example"
        combinations = [
            ["--publish-from", "/tmp/published.md"],
            ["--kindle-email", "reader@kindle.com"],
            ["--record-kindle-delivery", "gmail-message-123"],
            ["--inspect-only"],
            ["--force"],
            ["--output-dir", "/tmp/publication"],
        ]

        for extra in combinations:
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit) as context:
                    main(["--review-from", "/tmp/lesson.md", *extra, url])
                self.assertEqual(context.exception.code, 2)

    def test_review_from_uses_existing_workspace_without_acquisition(self) -> None:
        url = "https://www.youtube.com/watch?v=example"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir = self.make_workspace(root, url)
            lesson = root / "lesson.md"
            with (
                patch("gyte_study_tools.cli.inspect_video") as inspect_video,
                patch("gyte_study_tools.cli.prepare_transcript") as prepare_transcript,
                patch("gyte_study_tools.cli.ingest_article") as ingest_article,
                patch(
                    "gyte_study_tools.cli.review_lesson",
                    return_value=self.review_result(workdir),
                ) as review_lesson,
            ):
                result = main(
                    [
                        "--json",
                        "--review-from",
                        str(lesson),
                        "--work-root",
                        str(root),
                        url,
                    ]
                )

            self.assertEqual(result, 0)
            review_lesson.assert_called_once_with(workdir, lesson)
            inspect_video.assert_not_called()
            prepare_transcript.assert_not_called()
            ingest_article.assert_not_called()

    def test_publish_from_uses_existing_workspace_without_acquisition(self) -> None:
        url = "https://www.youtube.com/watch?v=example"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir = self.make_workspace(root, url)
            lesson = root / "lesson.md"
            with (
                patch("gyte_study_tools.cli.inspect_video") as inspect_video,
                patch("gyte_study_tools.cli.prepare_transcript") as prepare_transcript,
                patch("gyte_study_tools.cli.ingest_article") as ingest_article,
                patch(
                    "gyte_study_tools.cli.publish_lesson",
                    return_value=self.publication_result(workdir),
                ) as publish_lesson,
            ):
                result = main(
                    [
                        "--json",
                        "--publish-from",
                        str(lesson),
                        "--work-root",
                        str(root),
                        url,
                    ]
                )

            self.assertEqual(result, 0)
            publish_lesson.assert_called_once_with(
                workdir=workdir,
                source_path=lesson,
                author=DEFAULT_AUTHOR,
                output_dir=None,
            )
            inspect_video.assert_not_called()
            prepare_transcript.assert_not_called()
            ingest_article.assert_not_called()

    def test_existing_workspace_paths_work_for_article_urls(self) -> None:
        url = "https://example.test/article"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir = self.make_workspace(root, url)
            lesson = root / "article-lesson.md"
            with (
                patch("gyte_study_tools.cli.inspect_video") as inspect_video,
                patch("gyte_study_tools.cli.prepare_transcript") as prepare_transcript,
                patch("gyte_study_tools.cli.ingest_article") as ingest_article,
                patch(
                    "gyte_study_tools.cli.review_lesson",
                    return_value=self.review_result(workdir, source_type="article"),
                ) as review_lesson,
            ):
                result = main(
                    [
                        "--json",
                        "--review-from",
                        str(lesson),
                        "--work-root",
                        str(root),
                        url,
                    ]
                )

            self.assertEqual(result, 0)
            review_lesson.assert_called_once_with(workdir, lesson)
            inspect_video.assert_not_called()
            prepare_transcript.assert_not_called()
            ingest_article.assert_not_called()

    def test_normal_url_only_workflow_still_acquires(self) -> None:
        cases = (
            ("https://www.youtube.com/watch?v=example", "youtube"),
            ("https://example.test/article", "article"),
        )

        for url, source_type in cases:
            with self.subTest(source_type=source_type):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    workdir = root / "workspace"
                    with (
                        patch(
                            "gyte_study_tools.cli.inspect_video",
                            return_value=self.inspection_result(workdir),
                        ) as inspect_video,
                        patch(
                            "gyte_study_tools.cli.prepare_transcript",
                            return_value=self.preparation_result(workdir),
                        ) as prepare_transcript,
                        patch(
                            "gyte_study_tools.cli.ingest_article",
                            return_value=self.article_result(workdir),
                        ) as ingest_article,
                    ):
                        result = main(["--json", "--work-root", str(root), url])

                self.assertEqual(result, 0)
                if source_type == "youtube":
                    inspect_video.assert_called_once_with(url, root)
                    prepare_transcript.assert_called_once_with(workdir, force=False)
                    ingest_article.assert_not_called()
                else:
                    inspect_video.assert_not_called()
                    prepare_transcript.assert_not_called()
                    ingest_article.assert_called_once_with(
                        url=url,
                        work_root=root,
                        force=False,
                        inspect_only=False,
                    )


if __name__ == "__main__":
    unittest.main()
