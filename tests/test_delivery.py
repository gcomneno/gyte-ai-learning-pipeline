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
    def make_workspace(
        self,
        root: Path,
        publication_dir: Path | None = None,
    ) -> tuple[Path, str]:
        workdir = root / "workspace"
        workdir.mkdir(parents=True, exist_ok=True)
        publication = (
            publication_dir
            if publication_dir is not None
            else workdir / "publication"
        )
        publication.mkdir(parents=True)
        markdown_path = publication / "lesson.md"
        html_path = publication / "lesson.html"
        pdf_path = publication / "lesson.pdf"
        epub_path = publication / "lesson.epub"
        markdown_path.write_text(
            "# Lezione fixture\n\nContenuto revisionato sintetico.\n",
            encoding="utf-8",
        )
        html_path.write_text(
            "<!doctype html><html><body><h1>Lezione fixture</h1></body></html>\n",
            encoding="utf-8",
        )
        pdf_path.write_bytes(b"%PDF-fixture")
        with zipfile.ZipFile(epub_path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip")
            archive.writestr("content.txt", "EPUB fixture senza rete")
        source_url = "https://www.youtube.com/watch?v=fixture"
        metadata_path = workdir / "metadata.json"
        metadata_bytes = json.dumps(
            {
                "schema_version": 1,
                "source": {"requested_url": source_url},
                "video": {"id": "fixture"},
            }
        ).encode("utf-8") + b"\n"
        metadata_path.write_bytes(metadata_bytes)
        markdown_digest = hashlib.sha256(markdown_path.read_bytes()).hexdigest()
        epub_digest = hashlib.sha256(epub_path.read_bytes()).hexdigest()
        manifest_path = publication / "publication-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "published_at": "2026-08-24T00:00:00+00:00",
                    "title": "Lezione fixture",
                    "author": "Autore fixture",
                    "source_context": {
                        "relationship": "observed-at-publication-time",
                        "source_type": "youtube",
                        "source_id_kind": "youtube-video-id",
                        "source_id": "fixture",
                        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                        "prepared_artifacts": [],
                    },
                    "reviewed_source": {
                        "role": "reviewed-source-snapshot",
                        "sha256": markdown_digest,
                        "copied_to": "markdown",
                        "h1": "Lezione fixture",
                    },
                    "files": {
                        "markdown": {
                            "path": markdown_path.name,
                            "role": "reviewed-source-copy",
                            "sha256": markdown_digest,
                        },
                        "html": {
                            "path": html_path.name,
                            "role": "derived-publication-html",
                            "derived_from": "markdown",
                            "sha256": hashlib.sha256(
                                html_path.read_bytes()
                            ).hexdigest(),
                        },
                        "pdf": {
                            "path": pdf_path.name,
                            "role": "derived-publication-pdf",
                            "derived_from": "html",
                            "sha256": hashlib.sha256(
                                pdf_path.read_bytes()
                            ).hexdigest(),
                            "words": 4,
                        },
                        "epub": {
                            "path": epub_path.name,
                            "role": "derived-publication-epub",
                            "derived_from": "html",
                            "sha256": epub_digest,
                            "words": 4,
                        },
                    },
                    "source_words": 4,
                    "backups": {},
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

    def manifest_path(self, workdir: Path) -> Path:
        return workdir / "publication" / "publication-manifest.json"

    def read_manifest(self, workdir: Path) -> dict[str, object]:
        return json.loads(self.manifest_path(workdir).read_text(encoding="utf-8"))

    def write_manifest(self, workdir: Path, manifest: dict[str, object]) -> None:
        self.manifest_path(workdir).write_text(
            json.dumps(manifest) + "\n",
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

    def test_prepare_supports_publication_from_external_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publication_dir = root / "external-publication"
            workdir, _ = self.make_workspace(
                root,
                publication_dir=publication_dir,
            )
            result = prepare_kindle_delivery(workdir, "reader@kindle.com")

            self.assertEqual(
                Path(result.request["publication_manifest_path"]),
                publication_dir / "publication-manifest.json",
            )
            self.assertTrue(Path(result.request["attachment_path"]).is_file())
            self.assertEqual(result.request["video_id"], "fixture")

    def test_prepare_does_not_require_metadata_json_for_delivery_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            (workdir / "metadata.json").unlink()

            result = prepare_kindle_delivery(workdir, "reader@kindle.com")

            self.assertEqual(result.request["status"], "pending")
            self.assertEqual(result.request["video_id"], "fixture")

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
            manifest = self.read_manifest(workdir)
            manifest["source_context"]["source_type"] = "article"
            manifest["source_context"]["source_id_kind"] = "article-source-id"
            manifest["source_context"]["source_id"] = "article-fixture"
            self.write_manifest(workdir, manifest)

            delivery = prepare_kindle_delivery(workdir, "reader@kindle.com")
            self.assertEqual(delivery.request["source_type"], "article")
            self.assertEqual(delivery.request["source_id"], "article-fixture")

    def test_prepare_requires_completed_and_validated_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"]["publish"]["status"] = "pending"
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaises(DeliveryError):
                prepare_kindle_delivery(workdir, "reader@kindle.com")

    def test_prepare_rejects_legacy_or_missing_publication_manifest_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            manifest = self.read_manifest(workdir)

            for schema_version in (1, None):
                with self.subTest(schema_version=schema_version):
                    mutated = json.loads(json.dumps(manifest))
                    if schema_version is None:
                        del mutated["schema_version"]
                    else:
                        mutated["schema_version"] = schema_version
                    self.write_manifest(workdir, mutated)

                    with self.assertRaisesRegex(
                        DeliveryError,
                        "Manifest di pubblicazione legacy/non supportato",
                    ):
                        prepare_kindle_delivery(workdir, "reader@kindle.com")

    def test_prepare_rejects_state_epub_path_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            other_epub = workdir / "publication" / "other.epub"
            with zipfile.ZipFile(other_epub, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
            state_path = workdir / "pipeline-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["stages"]["publish"]["outputs"]["epub"] = str(other_epub)
            state_path.write_text(json.dumps(state) + "\n", encoding="utf-8")

            with self.assertRaises(DeliveryError):
                prepare_kindle_delivery(workdir, "reader@kindle.com")

    def test_prepare_rejects_unsafe_manifest_epub_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            manifest = self.read_manifest(workdir)

            for unsafe_path in ("../lesson.epub", str(workdir / "lesson.epub")):
                with self.subTest(unsafe_path=unsafe_path):
                    mutated = json.loads(json.dumps(manifest))
                    mutated["files"]["epub"]["path"] = unsafe_path
                    self.write_manifest(workdir, mutated)

                    with self.assertRaises(DeliveryError):
                        prepare_kindle_delivery(workdir, "reader@kindle.com")

    def test_prepare_rejects_tampered_published_epub(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            (workdir / "publication" / "lesson.epub").write_bytes(b"EPUB manomesso")

            with self.assertRaises(DeliveryError):
                prepare_kindle_delivery(workdir, "reader@kindle.com")

    def test_delivery_failure_does_not_rewrite_completed_publish_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workdir, _ = self.make_workspace(Path(temporary))
            state_path = workdir / "pipeline-state.json"
            before = json.loads(state_path.read_text(encoding="utf-8"))
            manifest = self.read_manifest(workdir)
            manifest["files"]["epub"]["sha256"] = "0" * 64
            self.write_manifest(workdir, manifest)

            with self.assertRaises(DeliveryError):
                prepare_kindle_delivery(workdir, "reader@kindle.com")

            after = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(after["stages"]["publish"], before["stages"]["publish"])
            self.assertEqual(after["stages"]["publish"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
