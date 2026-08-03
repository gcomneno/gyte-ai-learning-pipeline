"""Tests for the command-line interface."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC))

from gyte_study_tools import __version__  # noqa: E402
from gyte_study_tools.cli import REQUIRED_COMMANDS, build_parser  # noqa: E402
from gyte_study_tools.inspection import DEFAULT_WORK_ROOT  # noqa: E402


class CliTests(unittest.TestCase):
    def test_development_version_is_exposed(self) -> None:
        self.assertEqual(__version__, "0.3.0-dev")

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
        self.assertEqual(args.work_root, DEFAULT_WORK_ROOT)

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


if __name__ == "__main__":
    unittest.main()
