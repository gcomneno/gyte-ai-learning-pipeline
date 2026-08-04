"""Tests for the local Kindle delivery handoff."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC))

from gyte_study_tools.delivery import (  # noqa: E402
    DeliveryError,
    prepare_kindle_delivery,
    record_kindle_delivery,
    request_summary,
    request_id_for,
    resolve_workspace,
    validate_delivery_request,
    validate_kindle_email,
)


class DeliveryTests(unittest.TestCase):
    def make_workspace(self, root: Path) -> tuple[Path, str]:
        workdir = root / "workspace"
        publication = workdir / "publication"
        publication.mkdir(parents=True)
        epub_path = publication / "lesson.epub"
        with zipfile.ZipFile(epub_path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("content.txt", "EPUB fixture senza rete")
        digest = hashlib.sha256(epub_path.read_bytes()).hexdigest()
        manifest_path = publication / "publication-manifest.json"
        manifest_path.write_text(
            json.dumps({"files": {"epub": {"sha256": digest}}}) + "\n",
            encoding="utf-8",
        )
        source_url = "https://www.youtube.com/watch?v=fixture"
        (workdir / "metadata.json").write_text(
            json.dumps(
                {
                    "source": {"requested_url": source_url},
                    "video": {"id": "fixture"},
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
                        "publish": {
                            "status": "complete",
                            "outputs": {
                                "epub": str(epub_path),
                                "manifest": str(manifest_path),
                            },
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return workdir, source_url

    def request_path(self, workdir: Path) -> Path:
        return workdir / "delivery" / "kindle-delivery-request.json"

    def read_request(self, workdir: Path) -> dict[str, object]:
        return json.loads(self.request_path(workdir).read_text(encoding="utf-8"))

    def write_request(self, workdir: Path, request: dict[str, object]) -> None:
        self.request_path(workdir).write_text(
            json.dumps(request) + "\n",
            encoding="utf-8",
        )

    def assert_record_rejects(self, workdir: Path) -> None:
        try:
            record_kindle_delivery(workdir, "gmail-message-123")
        except DeliveryError:
            return
        except (KeyError, TypeError) as error:
            self.fail(f"Il confine DeliveryError ha lasciato uscire {error!r}")
        self.fail("La richiesta manomessa è stata accettata.")

    def test_valid_kindle_address_is_normalized(self) -> None:
        self.assertEqual(
            validate_kindle_email(" Reader@Kindle.Com "),
            "reader@kindle.com",
        )
        self.assertEqual(
            validate_kindle_email("reader@free.kindle.com"),
            "reader@free.kindle.com",
        )

    def test_non_kindle_domain_is_rejected(self) -> None:
        with self.assertRaises(DeliveryError):
            validate_kindle_email("reader@example.com")

    def test_prepare_creates_pending_request_and_stable_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            result = prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = result.request

            self.assertEqual(request["status"], "pending")
            self.assertEqual(request["handoff_mode"], "external-file-transfer")
            self.assertEqual(request["handoff_status"], "awaiting-transfer")
            self.assertEqual(request["provider"], "gmail-connector")
            self.assertEqual(request["video_id"], "fixture")
            self.assertTrue(request["request_id"].startswith("kindle-"))
            self.assertIn("created_at", request)
            self.assertIn("updated_at", request)
            self.assertIn("publication_manifest_path", request)
            self.assertTrue(Path(request["attachment_path"]).is_file())
            self.assertEqual(
                request["attachment_sha256"],
                hashlib.sha256(
                    Path(request["attachment_path"]).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                request["attachment_bytes"],
                Path(request["attachment_path"]).stat().st_size,
            )
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["stages"]["delivery"]["status"], "pending")
            self.assertEqual(
                state["stages"]["delivery"]["handoff_mode"],
                "external-file-transfer",
            )
            self.assertEqual(
                state["stages"]["delivery"]["handoff_status"],
                "awaiting-transfer",
            )
            self.assertEqual(
                state["stages"]["delivery"]["request_id"], request["request_id"]
            )

    def test_outbox_is_an_independent_copy_of_the_published_epub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            result = prepare_kindle_delivery(workdir, "reader@kindle.com")
            source = workdir / "publication" / "lesson.epub"
            attachment = Path(result.request["attachment_path"])
            source_before = source.read_bytes()

            self.assertNotEqual(source.stat().st_ino, attachment.stat().st_ino)
            attachment.write_bytes(b"solo la copia di prova dell'outbox")
            self.assertEqual(source.read_bytes(), source_before)

    def test_preparation_is_idempotent_for_same_recipient_and_epub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            first = prepare_kindle_delivery(workdir, "reader@kindle.com")
            second = prepare_kindle_delivery(workdir, "reader@kindle.com")

            self.assertEqual(first.request["request_id"], second.request["request_id"])
            self.assertEqual(first.request["created_at"], second.request["created_at"])

    def test_pending_request_repairs_missing_outbox_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            first = prepare_kindle_delivery(workdir, "reader@kindle.com")
            attachment = Path(first.request["attachment_path"])
            attachment.unlink()

            repeated = prepare_kindle_delivery(workdir, "reader@kindle.com")
            self.assertEqual(repeated.request["request_id"], first.request["request_id"])
            self.assertTrue(attachment.is_file())

    def test_pending_request_repairs_corrupt_outbox_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            first = prepare_kindle_delivery(workdir, "reader@kindle.com")
            attachment = Path(first.request["attachment_path"])
            attachment.write_bytes(b"EPUB corrotto")

            repeated = prepare_kindle_delivery(workdir, "reader@kindle.com")
            self.assertEqual(repeated.request["request_id"], first.request["request_id"])
            self.assertEqual(
                hashlib.sha256(attachment.read_bytes()).hexdigest(),
                first.request["attachment_sha256"],
            )

    def test_sent_request_is_not_implicitly_resent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            first = prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")
            repeated = prepare_kindle_delivery(workdir, "reader@kindle.com")

            self.assertEqual(repeated.request["status"], "sent")
            self.assertEqual(repeated.request["receipt"], "gmail-message-123")
            self.assertEqual(first.request["request_id"], repeated.request["request_id"])

    def test_sent_request_can_outlive_its_outbox_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            pending = prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")
            Path(pending.request["attachment_path"]).unlink()

            repeated = prepare_kindle_delivery(workdir, "reader@kindle.com")
            self.assertEqual(repeated.request["status"], "sent")

    def test_receipt_completes_pipeline_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            first = record_kindle_delivery(workdir, "gmail-message-123")
            repeated = record_kindle_delivery(workdir, "gmail-message-123")

            self.assertEqual(first.request["status"], "sent")
            self.assertEqual(first.request["handoff_status"], "connector-sent")
            self.assertEqual(repeated.request["receipt"], "gmail-message-123")
            state = json.loads(
                (workdir / "pipeline-state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["stages"]["delivery"]["status"], "complete")
            self.assertEqual(
                state["stages"]["delivery"]["handoff_mode"],
                "external-file-transfer",
            )
            self.assertEqual(
                state["stages"]["delivery"]["handoff_status"],
                "connector-sent",
            )
            self.assertEqual(
                state["stages"]["delivery"]["receipt"], "gmail-message-123"
            )
            self.assertIn("completed_at", state["stages"]["delivery"])

    def test_different_receipt_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")

            with self.assertRaises(DeliveryError):
                record_kindle_delivery(workdir, "gmail-message-456")

    def test_record_rejects_tampered_request_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["request_id"] = "kindle-tampered"
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_tampered_recipient(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["recipient"] = "other@kindle.com"
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_attachment_path_outside_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["attachment_path"] = str(workdir / "publication" / "lesson.epub")
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_symlinked_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            pending = prepare_kindle_delivery(workdir, "reader@kindle.com")
            attachment = Path(pending.request["attachment_path"])
            attachment.unlink()
            attachment.symlink_to(workdir / "publication" / "lesson.epub")

            self.assert_record_rejects(workdir)

    def test_record_rejects_tampered_attachment_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            pending = prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            tampered_hash = "0" * 64
            request["attachment_sha256"] = tampered_hash
            request["request_id"] = request_id_for("reader@kindle.com", tampered_hash)
            replacement = workdir / "delivery" / "outbox" / f"{request['request_id']}.epub"
            Path(pending.request["attachment_path"]).replace(replacement)
            request["attachment_path"] = str(replacement)
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_inconsistent_attachment_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["attachment_bytes"] = int(request["attachment_bytes"]) + 1
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_corrupt_outbox_epub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            pending = prepare_kindle_delivery(workdir, "reader@kindle.com")
            Path(pending.request["attachment_path"]).write_bytes(b"non un EPUB")

            self.assert_record_rejects(workdir)

    def test_record_rejects_sent_request_without_sent_at(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")
            request = self.read_request(workdir)
            del request["sent_at"]
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_sent_request_without_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")
            request = self.read_request(workdir)
            del request["receipt"]
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_missing_required_field_without_key_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            del request["subject"]
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_request_summary_includes_handoff_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            result = prepare_kindle_delivery(workdir, "reader@kindle.com")

            summary = request_summary(result)
            self.assertEqual(summary["handoff_mode"], "external-file-transfer")
            self.assertEqual(summary["handoff_status"], "awaiting-transfer")

    def test_record_rejects_tampered_handoff_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["handoff_mode"] = "direct-local-path"
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_pending_handoff_status_incoherent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = self.read_request(workdir)
            request["handoff_status"] = "connector-sent"
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_record_rejects_sent_handoff_status_incoherent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            prepare_kindle_delivery(workdir, "reader@kindle.com")
            record_kindle_delivery(workdir, "gmail-message-123")
            request = self.read_request(workdir)
            request["handoff_status"] = "awaiting-transfer"
            self.write_request(workdir, request)

            self.assert_record_rejects(workdir)

    def test_validate_rejects_malformed_handoff_without_type_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            result = prepare_kindle_delivery(workdir, "reader@kindle.com")
            request = dict(result.request)
            request["handoff_status"] = ["awaiting-transfer"]

            with self.assertRaises(DeliveryError):
                validate_delivery_request(
                    workdir, request, verify_pending_attachment=True
                )

    def test_resolve_workspace_uses_existing_metadata_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workdir, source_url = self.make_workspace(root)
            self.assertEqual(resolve_workspace(source_url, root), workdir)

    def test_synthetic_epub_pending_then_receipt_is_end_to_end_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            pending = prepare_kindle_delivery(workdir, "reader@kindle.com")
            complete = record_kindle_delivery(workdir, "synthetic-gmail-receipt")

            self.assertEqual(pending.request["status"], "pending")
            self.assertEqual(complete.request["status"], "sent")

    def test_prepare_preserves_article_source_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            metadata_path = workdir / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["source_type"] = "article"
            metadata_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")

            delivery = prepare_kindle_delivery(workdir, "reader@kindle.com")
            self.assertEqual(delivery.request["source_type"], "article")

    def test_prepare_requires_completed_and_validated_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"]["publish"]["status"] = "pending"
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaises(DeliveryError):
                prepare_kindle_delivery(workdir, "reader@kindle.com")


if __name__ == "__main__":
    unittest.main()
