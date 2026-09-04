"""Tests for validated repository handoff planning and application."""

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

from gyte_study_tools.handoff import (  # noqa: E402
    HandoffError,
    apply_handoff,
    prepare_handoff,
)


class HandoffTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        workdir = root / "workspace"
        checkout = root / "consumer"
        staging = workdir / "public-staging" / "physics-study"
        staging.mkdir(parents=True)
        checkout.mkdir()
        (checkout / ".git").mkdir()

        candidate = staging / "candidate.md"
        candidate.write_text(
            "# Public Candidate\n\n## Source basis\n\nSafe public content.\n",
            encoding="utf-8",
        )
        candidate_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        record = staging / "candidate.json"
        record.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "artifact": "public-lesson-candidate",
                    "authority": "staging-candidate",
                    "status": "complete",
                    "consumer": {
                        "consumer_id": "physics-study",
                        "domain": "physics",
                        "repository": "gcomneno/physics-study",
                        "base_branch": "main",
                        "target_relative_path": "lessons/public-candidate.md",
                    },
                    "candidate": "candidate.md",
                    "candidate_sha256": candidate_hash,
                    "boundary_scan": "passed",
                    "remote_write_authority": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "stages": {
                        "public_candidate": {
                            "status": "complete",
                            "consumer_id": "physics-study",
                            "candidate": "public-staging/physics-study/candidate.md",
                            "record": "public-staging/physics-study/candidate.json",
                            "candidate_sha256": candidate_hash,
                            "target_relative_path": "lessons/public-candidate.md",
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        contract = root / "contract.json"
        contract.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "consumer_id": "physics-study",
                    "domain": "physics",
                    "repository": "gcomneno/physics-study",
                    "base_branch": "main",
                    "output_root": "lessons",
                    "filename_template": "{slug}.md",
                    "local_checkout": str(checkout),
                    "validation_commands": [
                        ["python", "-m", "consumer_validation"]
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workdir, checkout, contract

    def command_result(self, cwd: Path, args: list[str], label: str) -> str:
        if args == ["git", "branch", "--show-current"]:
            return "main"
        if args == ["git", "rev-parse", "HEAD"]:
            return "a" * 40
        if args == ["git", "status", "--porcelain"]:
            return ""
        return ""

    def test_prepare_creates_preview_without_mutating_consumer_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, checkout, contract = self.make_fixture(root)
            target = checkout / "lessons/public-candidate.md"

            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=self.command_result,
            ):
                result = prepare_handoff(workdir, contract)

            self.assertFalse(target.exists())
            self.assertTrue(result.plan_path.is_file())
            self.assertTrue(result.preview_path.is_file())
            plan = json.loads(result.plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["authority"], "publication-approval-required")
            self.assertFalse(plan["remote_write_authority"])
            self.assertEqual(plan["base_head"], "a" * 40)
            self.assertIn("public-candidate.md", result.preview_path.read_text(encoding="utf-8"))

    def test_wrong_approval_rejects_before_repository_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, checkout, contract = self.make_fixture(root)
            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=self.command_result,
            ):
                plan = prepare_handoff(workdir, contract)

            target = checkout / "lessons/public-candidate.md"
            with patch("gyte_study_tools.handoff.run_command") as command:
                with self.assertRaises(HandoffError):
                    apply_handoff(plan.plan_path, approval="wrong")
            command.assert_not_called()
            self.assertFalse(target.exists())

    def test_approved_handoff_validates_before_push_and_creates_pr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, checkout, contract = self.make_fixture(root)
            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=self.command_result,
            ):
                plan = prepare_handoff(workdir, contract)

            calls: list[list[str]] = []

            def apply_command(cwd: Path, args: list[str], label: str) -> str:
                calls.append(args)
                if args == ["git", "branch", "--show-current"]:
                    return "main"
                if args == ["git", "rev-parse", "HEAD"]:
                    # First call is preflight HEAD; second is post-commit SHA.
                    count = sum(call == args for call in calls)
                    return "a" * 40 if count == 1 else "c" * 40
                if args == ["git", "status", "--porcelain"]:
                    return ""
                if args[:3] == ["gh", "pr", "create"]:
                    return "https://github.com/gcomneno/physics-study/pull/123"
                return ""

            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=apply_command,
            ):
                result = apply_handoff(plan.plan_path, approval=plan.plan_id)

            target = checkout / "lessons/public-candidate.md"
            self.assertTrue(target.is_file())
            self.assertEqual(result.commit_sha, "c" * 40)
            self.assertEqual(
                result.pull_request_url,
                "https://github.com/gcomneno/physics-study/pull/123",
            )
            validation_index = calls.index(["python", "-m", "consumer_validation"])
            push_index = next(i for i, command in enumerate(calls) if command[:3] == ["git", "push", "-u"])
            self.assertLess(validation_index, push_index)
            self.assertFalse(
                json.loads(result.result_path.read_text(encoding="utf-8"))["merge_authority"]
            )

    def test_validation_failure_records_retry_state_and_does_not_push(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, checkout, contract = self.make_fixture(root)
            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=self.command_result,
            ):
                plan = prepare_handoff(workdir, contract)

            calls: list[list[str]] = []

            def failing_command(cwd: Path, args: list[str], label: str) -> str:
                calls.append(args)
                if args == ["git", "branch", "--show-current"]:
                    return "main"
                if args == ["git", "rev-parse", "HEAD"]:
                    return "a" * 40
                if args == ["git", "status", "--porcelain"]:
                    return ""
                if args == ["python", "-m", "consumer_validation"]:
                    raise HandoffError("consumer failed", step="consumer-validation")
                return ""

            with patch(
                "gyte_study_tools.handoff.run_command",
                side_effect=failing_command,
            ):
                with self.assertRaises(HandoffError):
                    apply_handoff(plan.plan_path, approval=plan.plan_id)

            self.assertFalse(any(command[:3] == ["git", "push", "-u"] for command in calls))
            result_path = plan.plan_path.with_name("result.json")
            failure = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "failed")
            self.assertEqual(failure["step"], "consumer-validation")
            self.assertFalse(failure["progress"]["pushed"])
            self.assertEqual(failure["retry"]["base_head"], "a" * 40)


if __name__ == "__main__":
    unittest.main()
