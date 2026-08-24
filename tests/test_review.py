"""Tests for reviewed-source checkpoint."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gyte_study_tools import review as review_module  # noqa: E402
from gyte_study_tools.review import (  # noqa: E402
    ReviewError,
    review_lesson,
    validate_review_checkpoint,
)


class ReviewTests(unittest.TestCase):
    def workspace(self, root: Path) -> tuple[Path, Path]:
        workdir = root / "w"
        workdir.mkdir()

        (workdir / "metadata.json").write_text(
            json.dumps(
                {
                    "video": {
                        "id": "v",
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )

        for name in (
            "source-url.txt",
            "transcript.raw.txt",
            "transcript.normalized.txt",
            "transcript.analysis.txt",
            "transcript.analysis.md",
        ):
            (workdir / name).write_text(
                "x\n",
                encoding="utf-8",
            )

        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "video_id": "v",
                    "stages": {
                        "prepare": {
                            "status": "complete",
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        lesson = root / "lesson.md"
        lesson.write_text(
            "# H1\n\nBody\n",
            encoding="utf-8",
        )

        return workdir, lesson

    def article_workspace(self, root: Path) -> tuple[Path, Path]:
        workdir = root / "article-workspace"
        workdir.mkdir()
        (workdir / "metadata.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source_type": "article",
                    "source": {"requested_url": "https://example.test/article"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        for name in (
            "source-url.txt",
            "article.raw.html",
            "article.extracted.md",
            "article.analysis.md",
        ):
            (workdir / name).write_text("article fixture\n", encoding="utf-8")
        (workdir / "pipeline-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source_type": "article",
                    "source_id": "article-fixture",
                    "stages": {"prepare": {"status": "complete"}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        lesson = root / "article-lesson.md"
        lesson.write_text("# Article H1\n\nBody\n", encoding="utf-8")
        return workdir, lesson

    def refresh_state_checkpoint_hash(self, workdir: Path) -> None:
        checkpoint_path = workdir / "reviewed-source-checkpoint.json"
        state_path = workdir / "pipeline-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stages"]["review"]["checkpoint_sha256"] = hashlib.sha256(
            checkpoint_path.read_bytes()
        ).hexdigest()
        state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

    def test_review_creates_checkpoint_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))

            result = review_lesson(workdir, lesson)

            self.assertTrue(result.checkpoint_path.is_file())
            validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_missing_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            (workdir / "transcript.raw.txt").unlink()

            with self.assertRaisesRegex(
                ReviewError,
                "stale evidence/preparation",
            ):
                review_lesson(workdir, lesson)

    def test_review_rejects_stale_reviewed_lesson(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))

            review_lesson(workdir, lesson)

            lesson.write_text(
                "# H1\n\nchanged\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ReviewError,
                "stale reviewed lesson",
            ):
                validate_review_checkpoint(workdir, lesson)


    def test_review_rejects_unsupported_schema_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)

            checkpoint_path = workdir / "reviewed-source-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["schema_version"] = True

            data = json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n"
            checkpoint_path.write_text(data, encoding="utf-8")

            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            import hashlib
            state["stages"]["review"]["checkpoint_sha256"] = hashlib.sha256(
                data.encode("utf-8")
            ).hexdigest()
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ReviewError,
                "schema o operation",
            ):
                validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_tampered_checkpoint_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)

            checkpoint_path = workdir / "reviewed-source-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["checkpoint_id"] = "review-not-a-valid-id"

            data = json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n"
            checkpoint_path.write_text(data, encoding="utf-8")

            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            import hashlib
            state["stages"]["review"]["checkpoint_sha256"] = hashlib.sha256(
                data.encode("utf-8")
            ).hexdigest()
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(
                ReviewError,
                "checkpoint_id",
            ):
                validate_review_checkpoint(workdir, lesson)

    def test_review_state_remains_coherent_if_state_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))

            first = review_lesson(workdir, lesson)
            previous_checkpoint = first.checkpoint_path.read_bytes()
            previous_state = (
                workdir / "pipeline-state.json"
            ).read_bytes()

            lesson.write_text(
                "# H1\n\nChanged for rereview.\n",
                encoding="utf-8",
            )

            real_atomic_write_text = review_module.atomic_write_text

            def fail_state_write(path, content):
                if Path(path).name == "pipeline-state.json":
                    raise OSError("synthetic state write failure")
                return real_atomic_write_text(path, content)

            with patch(
                "gyte_study_tools.review.atomic_write_text",
                side_effect=fail_state_write,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "synthetic state write failure",
                ):
                    review_lesson(workdir, lesson)

            self.assertEqual(
                first.checkpoint_path.read_bytes(),
                previous_checkpoint,
            )
            self.assertEqual(
                (workdir / "pipeline-state.json").read_bytes(),
                previous_state,
            )

            lesson.write_text(
                "# H1\n\nBody\n",
                encoding="utf-8",
            )
            validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_multiple_h1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            lesson.write_text("# First\n\n# Second\n", encoding="utf-8")

            with self.assertRaisesRegex(ReviewError, "esattamente un"):
                review_lesson(workdir, lesson)

    def test_review_requires_prepare_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"]["prepare"]["status"] = "pending"
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ReviewError, "prepare"):
                review_lesson(workdir, lesson)

    def test_review_creates_complete_video_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            result = review_lesson(workdir, lesson)

            self.assertEqual(
                result.checkpoint["source_identity"],
                {
                    "source_type": "youtube",
                    "source_id_kind": "youtube-video-id",
                    "source_id": "v",
                },
            )
            self.assertEqual(
                [(item["name"], item["role"]) for item in result.checkpoint["bound_artifacts"]],
                [
                    ("metadata.json", "source-metadata"),
                    ("source-url.txt", "source-url"),
                    ("transcript.raw.txt", "source-evidence"),
                    ("transcript.normalized.txt", "normalized-evidence"),
                    ("transcript.analysis.txt", "prepared-analysis"),
                    ("transcript.analysis.md", "prepared-analysis"),
                ],
            )

    def test_review_creates_complete_article_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.article_workspace(Path(temporary))
            result = review_lesson(workdir, lesson)

            self.assertEqual(
                result.checkpoint["source_identity"],
                {
                    "source_type": "article",
                    "source_id_kind": "article-source-id",
                    "source_id": "article-fixture",
                },
            )
            self.assertEqual(
                [(item["name"], item["role"]) for item in result.checkpoint["bound_artifacts"]],
                [
                    ("metadata.json", "source-metadata"),
                    ("source-url.txt", "source-url"),
                    ("article.raw.html", "source-evidence"),
                    ("article.extracted.md", "normalized-evidence"),
                    ("article.analysis.md", "prepared-analysis"),
                ],
            )

    def test_review_rejects_symlink_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            (workdir / "transcript.raw.txt").unlink()
            (workdir / "transcript.raw.txt").symlink_to(workdir / "source-url.txt")

            with self.assertRaisesRegex(ReviewError, "symlink"):
                review_lesson(workdir, lesson)

    def test_review_rejects_empty_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            (workdir / "transcript.raw.txt").write_text("", encoding="utf-8")

            with self.assertRaisesRegex(ReviewError, "assente o vuoto"):
                review_lesson(workdir, lesson)

    def test_review_rejects_malformed_checkpoint_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            (workdir / "reviewed-source-checkpoint.json").write_text(
                "{not json\n", encoding="utf-8"
            )
            self.refresh_state_checkpoint_hash(workdir)

            with self.assertRaisesRegex(ReviewError, "checkpoint illeggibile"):
                validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_invalid_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            checkpoint_path = workdir / "reviewed-source-checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["operation"] = "automatic-review"
            checkpoint_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.refresh_state_checkpoint_hash(workdir)

            with self.assertRaisesRegex(ReviewError, "schema o operation"):
                validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_state_checkpoint_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            checkpoint_path = workdir / "reviewed-source-checkpoint.json"
            checkpoint_path.write_text(
                checkpoint_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "state/checkpoint hash mismatch"):
                validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_source_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            (workdir / "metadata.json").write_text(
                json.dumps({"video": {"id": "changed"}}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ReviewError, "source identity mismatch"):
                validate_review_checkpoint(workdir, lesson)

    def test_review_rejects_state_review_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"]["review"]["source_id"] = "changed"
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ReviewError, "source identity mismatch"):
                validate_review_checkpoint(workdir, lesson)

    def test_rereview_restores_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, lesson = self.workspace(Path(temporary))
            review_lesson(workdir, lesson)
            (workdir / "transcript.raw.txt").write_text(
                "changed evidence\n", encoding="utf-8"
            )

            with self.assertRaisesRegex(ReviewError, "stale evidence/preparation"):
                validate_review_checkpoint(workdir, lesson)

            review_lesson(workdir, lesson)
            validate_review_checkpoint(workdir, lesson)


if __name__ == "__main__":
    unittest.main()
