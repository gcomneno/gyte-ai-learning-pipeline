"""Tests for private structured fact-check reporting."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from gyte_study_tools.fact_check import (  # noqa: E402
    FactCheckError,
    claim_id,
    generate_fact_check_report,
)


class FactCheckTests(unittest.TestCase):
    def make_workspace(self, root: Path, *, with_candidate: bool = True) -> Path:
        workdir = root / "workspace"
        workdir.mkdir()
        (workdir / "transcript.analysis.md").write_text(
            "# Prepared\n\nThe system always uses exactly 42 units. "
            "This behavior may depend on configuration.\n",
            encoding="utf-8",
        )
        state = {
            "schema_version": 1,
            "video_id": "fixture",
            "stages": {"prepare": {"status": "complete"}},
        }
        if with_candidate:
            candidate = workdir / "editorial-candidate.md"
            candidate.write_text(
                "# Candidate\n\nThe system always uses exactly 42 units. "
                "This behavior may depend on configuration.\n",
                encoding="utf-8",
            )
            import hashlib

            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            state["stages"]["candidate"] = {
                "status": "complete",
                "candidate": candidate.name,
                "candidate_sha256": digest,
            }
        (workdir / "pipeline-state.json").write_text(
            json.dumps(state) + "\n",
            encoding="utf-8",
        )
        return workdir

    def test_report_prefers_current_candidate_and_keeps_claims_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary))
            result = generate_fact_check_report(workdir)
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )

            self.assertEqual(result.input_path.name, "editorial-candidate.md")
            self.assertEqual(report["authority"], "fact-check-advisory")
            self.assertGreaterEqual(result.claim_count, 1)
            self.assertEqual(result.unresolved_count, result.claim_count)
            self.assertTrue(all(claim["status"] == "unresolved" for claim in report["claims"]))
            self.assertTrue(all(claim["references"] == [] for claim in report["claims"]))
            self.assertFalse(report["authority_boundary"]["review_granted"])
            self.assertFalse(state["stages"]["fact_check"]["review_granted"])
            self.assertNotIn("review", state["stages"])

    def test_evidence_records_support_and_references_without_mutating_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary), with_candidate=False)
            input_path = workdir / "transcript.analysis.md"
            before = input_path.read_bytes()
            claim_text = (
                "The system always uses exactly 42 units. "
                "This behavior may depend on configuration."
            )
            identifier = claim_id(claim_text)
            evidence = workdir / "evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claims": {
                            identifier: {
                                "status": "supported",
                                "references": ["https://example.invalid/reference"],
                                "editorial_qualification": "Supported for the declared configuration only.",
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = generate_fact_check_report(workdir, evidence_path=evidence)
            report = json.loads(result.report_path.read_text(encoding="utf-8"))

            self.assertEqual(input_path.read_bytes(), before)
            self.assertEqual(report["claims"][0]["status"], "supported")
            self.assertEqual(
                report["claims"][0]["references"],
                ["https://example.invalid/reference"],
            )
            self.assertEqual(result.unresolved_count, 0)

    def test_non_unresolved_status_requires_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary), with_candidate=False)
            claim_text = (
                "The system always uses exactly 42 units. "
                "This behavior may depend on configuration."
            )
            evidence = workdir / "evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claims": {
                            claim_id(claim_text): {
                                "status": "supported",
                                "references": [],
                                "editorial_qualification": "none",
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(FactCheckError):
                generate_fact_check_report(workdir, evidence_path=evidence)

    def test_report_requires_completed_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = self.make_workspace(Path(temporary), with_candidate=False)
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"].pop("prepare")
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaises(FactCheckError):
                generate_fact_check_report(workdir)


if __name__ == "__main__":
    unittest.main()
