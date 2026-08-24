"""Tests for optional AI advisory artifacts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC))

from gyte_study_tools.ai_advisory import (  # noqa: E402
    ADVISORY_ARTIFACT,
    ADVISORY_FILENAME,
    AIAdvisoryError,
    AIAdvisoryFailure,
    generate_ai_advisory,
    serialize_learning_source_analysis,
)


class SyntheticSupport(Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    UNCLEAR = "unclear"


def make_analysis(*, supports: tuple[object, ...] = (SyntheticSupport.EXPLICIT,)) -> SimpleNamespace:
    return SimpleNamespace(
        central_thesis="The source explains semantic AI boundaries.",
        key_concepts=["semantic capability", "consumer contract"],
        source_claims=[
            SimpleNamespace(
                claim=f"Claim {index}",
                support=support,
            )
            for index, support in enumerate(supports, start=1)
        ],
        practical_applications=["Keep AI output advisory."],
        limitations=["The source does not prove external truth."],
        review_questions=["Which layer owns authority?"],
    )


class AIAdvisoryTests(unittest.TestCase):
    def write_input(
        self,
        workdir: Path,
        *,
        source_type: str = "youtube",
        content: bytes = b"# Analysis\n\nPrepared source.\n",
    ) -> Path:
        name = (
            "article.analysis.md"
            if source_type == "article"
            else "transcript.analysis.md"
        )
        path = workdir / name
        path.write_bytes(content)
        return path

    def test_writes_filename_distinct_from_artifact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            result = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=lambda text: make_analysis(),
            )

            self.assertEqual(result.path, workdir / ADVISORY_FILENAME)
            self.assertTrue((workdir / ADVISORY_FILENAME).is_file())
            self.assertFalse((workdir / ADVISORY_ARTIFACT).exists())
            self.assertEqual(result.envelope["artifact"], ADVISORY_ARTIFACT)

    def test_success_envelope_uses_stable_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            input_path = self.write_input(workdir, source_type="article")

            result = generate_ai_advisory(
                workdir,
                "article",
                analyzer=lambda text: make_analysis(),
            )

            envelope = json.loads(result.path.read_text(encoding="utf-8"))
            self.assertEqual(envelope["schema_version"], 1)
            self.assertEqual(envelope["artifact"], "learning-source.analysis.ai")
            self.assertEqual(envelope["authority"], "ai-advisory")
            self.assertEqual(envelope["status"], "complete")
            self.assertEqual(
                envelope["provenance"]["source_type"],
                "article",
            )
            self.assertEqual(
                envelope["provenance"]["canonical_input"],
                input_path.name,
            )
            self.assertEqual(
                envelope["provenance"]["canonical_input_byte_count"],
                input_path.stat().st_size,
            )
            self.assertIn("canonical_input_sha256", envelope["provenance"])
            self.assertIsNone(envelope["failure"])
            self.assertIsInstance(envelope["payload"], dict)
            self.assertNotIn("analysis", envelope)
            self.assertNotEqual(envelope["status"], "succeeded")

    def test_all_learning_source_fields_serialize(self) -> None:
        payload = serialize_learning_source_analysis(make_analysis())

        self.assertEqual(
            list(payload),
            [
                "central_thesis",
                "key_concepts",
                "source_claims",
                "practical_applications",
                "limitations",
                "review_questions",
            ],
        )

    def test_source_claim_and_support_values_serialize(self) -> None:
        payload = serialize_learning_source_analysis(
            make_analysis(
                supports=(
                    SyntheticSupport.EXPLICIT,
                    SyntheticSupport.INFERRED,
                    SyntheticSupport.UNCLEAR,
                )
            )
        )

        self.assertEqual(
            payload["source_claims"],
            [
                {"claim": "Claim 1", "support": "explicit"},
                {"claim": "Claim 2", "support": "inferred"},
                {"claim": "Claim 3", "support": "unclear"},
            ],
        )

    def test_equivalent_structural_mapping_fixture_serializes(self) -> None:
        payload = serialize_learning_source_analysis(
            {
                "central_thesis": "A thesis",
                "key_concepts": ["concept"],
                "source_claims": [
                    {
                        "claim": "A claim",
                        "support": "explicit",
                    }
                ],
                "practical_applications": ["application"],
                "limitations": ["limitation"],
                "review_questions": ["question"],
            }
        )

        self.assertEqual(payload["source_claims"][0]["support"], "explicit")

    def test_arbitrary_mapping_cannot_become_successful_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            with self.assertRaises(AIAdvisoryError):
                generate_ai_advisory(
                    workdir,
                    "youtube",
                    analyzer=lambda text: {"anything": "..."},
                )

            self.assertFalse((workdir / ADVISORY_FILENAME).exists())

    def test_invalid_structural_shape_fails_closed(self) -> None:
        with self.assertRaises(AIAdvisoryError):
            serialize_learning_source_analysis(
                {
                    "central_thesis": "A thesis",
                    "key_concepts": ["concept"],
                    "source_claims": [
                        {
                            "claim": "A claim",
                            "support": "verified",
                        }
                    ],
                    "practical_applications": ["application"],
                    "limitations": ["limitation"],
                    "review_questions": ["question"],
                }
            )

    def test_expected_failure_is_persisted_without_provider_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            def analyzer(text: str) -> object:
                raise AIAdvisoryFailure(
                    "invalid-response",
                    "bad model output",
                )

            result = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=analyzer,
            )

            self.assertEqual(result.envelope["status"], "failed")
            self.assertIsNone(result.envelope["payload"])
            self.assertEqual(
                result.envelope["failure"],
                {
                    "kind": "invalid-response",
                    "message": "bad model output",
                },
            )

    def test_success_preserves_review_publish_delivery_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            state_path = workdir / "pipeline-state.json"
            checkpoint_path = workdir / "reviewed-source-checkpoint.json"

            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stages": {
                            "prepare": {"status": "complete"},
                            "review": {"status": "complete"},
                            "publish": {"status": "complete"},
                            "delivery": {"status": "pending"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            checkpoint_path.write_bytes(
                b'{"schema_version":1,"operation":"reviewed-source-checkpoint"}\n'
            )

            state_before = state_path.read_bytes()
            checkpoint_before = checkpoint_path.read_bytes()

            result = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=lambda text: make_analysis(),
            )

            self.assertEqual(result.envelope["status"], "complete")
            self.assertEqual(state_path.read_bytes(), state_before)
            self.assertEqual(checkpoint_path.read_bytes(), checkpoint_before)
            self.assertFalse((workdir / "lesson.md").exists())
            self.assertFalse((workdir / "publication").exists())
            self.assertFalse((workdir / "delivery").exists())

    def test_expected_failure_preserves_review_publish_delivery_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            state_path = workdir / "pipeline-state.json"
            checkpoint_path = workdir / "reviewed-source-checkpoint.json"

            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stages": {
                            "prepare": {"status": "complete"},
                            "review": {"status": "complete"},
                            "publish": {"status": "complete"},
                            "delivery": {"status": "pending"},
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            checkpoint_path.write_bytes(
                b'{"schema_version":1,"operation":"reviewed-source-checkpoint"}\n'
            )

            state_before = state_path.read_bytes()
            checkpoint_before = checkpoint_path.read_bytes()

            def analyzer(text: str) -> object:
                raise AIAdvisoryFailure("timeout", "synthetic timeout")

            result = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=analyzer,
            )

            self.assertEqual(result.envelope["status"], "failed")
            self.assertEqual(
                result.envelope["failure"]["kind"],
                "timeout",
            )
            self.assertEqual(state_path.read_bytes(), state_before)
            self.assertEqual(checkpoint_path.read_bytes(), checkpoint_before)
            self.assertFalse((workdir / "lesson.md").exists())
            self.assertFalse((workdir / "publication").exists())
            self.assertFalse((workdir / "delivery").exists())

    def test_failed_artifact_is_not_reused_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            self.write_input(workdir)

            def unavailable(text: str) -> object:
                raise AIAdvisoryFailure("unavailable", "offline")

            first = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=unavailable,
            )
            self.assertEqual(first.envelope["status"], "failed")

            calls = 0

            def successful(text: str) -> object:
                nonlocal calls
                calls += 1
                return make_analysis()

            second = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=successful,
            )

            self.assertEqual(calls, 1)
            self.assertEqual(second.envelope["status"], "complete")
            self.assertFalse(second.reused)

    def test_complete_artifact_reuse_requires_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            input_path = self.write_input(workdir, content=b"Alpha beta\n")

            first = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=lambda text: make_analysis(),
            )

            second = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=lambda text: self.fail("reusable success should not call AI"),
            )
            self.assertTrue(second.reused)
            self.assertEqual(second.envelope["payload"], first.envelope["payload"])

            input_path.write_bytes(b"Alpha zeta\n")
            self.assertEqual(len(b"Alpha beta\n"), len(b"Alpha zeta\n"))

            calls = 0

            def changed(text: str) -> object:
                nonlocal calls
                calls += 1
                return make_analysis()

            third = generate_ai_advisory(
                workdir,
                "youtube",
                analyzer=changed,
            )

            self.assertEqual(calls, 1)
            self.assertFalse(third.reused)

    def test_rejects_invalid_canonical_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir = Path(temporary)
            (workdir / "transcript.analysis.md").write_bytes(b"\xff")

            with self.assertRaises(AIAdvisoryError):
                generate_ai_advisory(
                    workdir,
                    "youtube",
                    analyzer=lambda text: make_analysis(),
                )


if __name__ == "__main__":
    unittest.main()
