"""Tests for private editorial-candidate generation."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from gyte_study_tools.editorial_candidate import (  # noqa: E402
    EditorialCandidateError,
    generate_editorial_candidate,
)
from gyte_study_tools.publishing import PublicationError, publish_lesson  # noqa: E402
from gyte_study_tools.review import review_lesson  # noqa: E402


class EditorialCandidateTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> Path:
        workdir = root / "workspace"
        workdir.mkdir()
        (workdir / "metadata.json").write_text(
            json.dumps(
                {
                    "video": {"id": "fixture", "title": "Candidate Fixture"},
                    "source": {"requested_url": "https://example.invalid/video"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workdir / "source-url.txt").write_text(
            "https://example.invalid/video\n",
            encoding="utf-8",
        )
        for name, text in (
            ("transcript.raw.txt", "raw evidence\n"),
            ("transcript.normalized.txt", "normalized evidence\n"),
            ("transcript.analysis.txt", "prepared analysis\n"),
            ("transcript.analysis.md", "# Prepared\n\nPrepared analysis body.\n"),
        ):
            (workdir / name).write_text(text, encoding="utf-8")
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "video_id": "fixture",
                    "stages": {"prepare": {"status": "complete"}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workdir

    def test_generation_records_distinct_candidate_authority_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            result = generate_editorial_candidate(workdir)
            record = json.loads(result.record_path.read_text(encoding="utf-8"))
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )

            self.assertFalse(result.reused)
            self.assertEqual(record["artifact"], "editorial-candidate")
            self.assertEqual(record["authority"], "candidate")
            self.assertEqual(record["promotion"]["required_operation"], "reviewed-source-checkpoint")
            self.assertFalse(record["promotion"]["automatic"])
            self.assertEqual(state["stages"]["candidate"]["authority"], "candidate")
            self.assertEqual(
                record["provenance"]["canonical_input"],
                "transcript.analysis.md",
            )
            self.assertEqual(
                record["candidate_sha256"],
                hashlib.sha256(result.candidate_path.read_bytes()).hexdigest(),
            )

    def test_same_prepared_input_reuses_exact_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            first = generate_editorial_candidate(workdir)
            first_bytes = first.candidate_path.read_bytes()
            second = generate_editorial_candidate(workdir)

            self.assertTrue(second.reused)
            self.assertEqual(second.candidate_path.read_bytes(), first_bytes)
            self.assertEqual(second.candidate_sha256, first.candidate_sha256)

    def test_changed_prepared_input_invalidates_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            first = generate_editorial_candidate(workdir)
            (workdir / "transcript.analysis.md").write_text(
                "# Prepared\n\nChanged prepared analysis.\n",
                encoding="utf-8",
            )
            second = generate_editorial_candidate(workdir)

            self.assertFalse(second.reused)
            self.assertNotEqual(second.input_sha256, first.input_sha256)

    def test_candidate_requires_prepare_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"].pop("prepare")
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaises(EditorialCandidateError):
                generate_editorial_candidate(workdir)

    def test_candidate_has_no_publish_authority_until_explicit_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            result = generate_editorial_candidate(workdir)

            with patch("gyte_study_tools.publishing.build_converted_outputs") as conversion:
                with self.assertRaises(PublicationError):
                    publish_lesson(workdir, result.candidate_path)
            conversion.assert_not_called()

            review = review_lesson(workdir, result.candidate_path)
            self.assertEqual(
                review.checkpoint["reviewed_source"]["role"],
                "reviewed-source-snapshot",
            )
            self.assertNotEqual(
                review.checkpoint["reviewed_source"]["role"],
                "editorial-candidate",
            )


if __name__ == "__main__":
    unittest.main()
