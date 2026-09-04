"""Tests for consumer contracts and public-safe staging candidates."""

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

from gyte_study_tools.consumers import (  # noqa: E402
    ConsumerContractError,
    boundary_scan,
    generate_public_candidate,
    load_consumer_contract,
)


class ConsumerContractTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> tuple[Path, Path]:
        workdir = root / "workspace"
        workdir.mkdir()
        (workdir / "metadata.json").write_text(
            json.dumps(
                {
                    "video": {"id": "fixture", "title": "Quantum Fixture"},
                    "source": {
                        "requested_url": "https://example.invalid/quantum-fixture",
                        "webpage_url": "https://example.invalid/quantum-fixture",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "video_id": "fixture",
                    "stages": {
                        "prepare": {"status": "complete"},
                        "review": {"status": "complete"},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        reviewed = workdir / "lesson.md"
        reviewed.write_text(
            "# Quantum Lesson\n\n"
            "Private reviewed body that must not be copied verbatim.\n\n"
            "## First principle\n\nDetailed private explanation.\n\n"
            "## Limits\n\nMore private detail.\n",
            encoding="utf-8",
        )
        return workdir, reviewed

    def write_contract(self, root: Path, *, consumer_id: str = "physics-study") -> Path:
        contract = root / f"{consumer_id}.json"
        contract.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "consumer_id": consumer_id,
                    "domain": "physics" if consumer_id == "physics-study" else "other",
                    "repository": f"gcomneno/{consumer_id}",
                    "base_branch": "main",
                    "output_root": "lessons",
                    "filename_template": "{slug}.md",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return contract

    def test_reviewed_source_routes_to_configured_consumer_without_copying_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, reviewed = self.make_workspace(root)
            contract = self.write_contract(root)

            with patch(
                "gyte_study_tools.consumers.validate_review_checkpoint",
                return_value=SimpleNamespace(checkpoint_sha256="a" * 64),
            ):
                result = generate_public_candidate(workdir, reviewed, contract)

            candidate = result.candidate_path.read_text(encoding="utf-8")
            record = json.loads(result.record_path.read_text(encoding="utf-8"))
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )

            self.assertEqual(result.contract.repository, "gcomneno/physics-study")
            self.assertEqual(result.target_relative_path, "lessons/quantum-lesson.md")
            self.assertIn("First principle", candidate)
            self.assertIn("Limits", candidate)
            self.assertNotIn("Private reviewed body that must not be copied verbatim.", candidate)
            self.assertNotIn("Detailed private explanation.", candidate)
            self.assertEqual(record["boundary_scan"], "passed")
            self.assertEqual(record["authority"], "staging-candidate")
            self.assertFalse(record["remote_write_authority"])
            self.assertFalse(state["stages"]["public_candidate"]["remote_write_authority"])

    def test_core_accepts_non_physics_consumer_without_domain_hard_coding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, reviewed = self.make_workspace(root)
            contract = self.write_contract(root, consumer_id="systems-study")

            with patch(
                "gyte_study_tools.consumers.validate_review_checkpoint",
                return_value=SimpleNamespace(checkpoint_sha256="b" * 64),
            ):
                result = generate_public_candidate(workdir, reviewed, contract)

            self.assertEqual(result.contract.domain, "other")
            self.assertEqual(result.contract.repository, "gcomneno/systems-study")

    def test_boundary_scan_rejects_private_artifact_names_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary) / "private"
            workdir.mkdir()
            with self.assertRaises(ConsumerContractError):
                boundary_scan(
                    f"Do not publish transcript.raw.txt from {workdir}",
                    workdir=workdir,
                )

    def test_contract_rejects_unsafe_target_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "unsafe.json"
            contract.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "consumer_id": "unsafe",
                        "domain": "fixture",
                        "repository": "gcomneno/unsafe",
                        "base_branch": "main",
                        "output_root": "lessons",
                        "filename_template": "../{slug}.md",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConsumerContractError):
                load_consumer_contract(contract)


if __name__ == "__main__":
    unittest.main()
