"""Local handoff for sending a validated EPUB through the Gmail connector.

This module never accesses Gmail.  It creates a durable request that an
external connector can act on, then records that connector's receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state
from gyte_study_tools.publishing import (
    PublicationError,
    sha256_file,
    validate_epub,
)


REQUEST_FILENAME = "kindle-delivery-request.json"
PROVIDER = "gmail-connector"
HANDOFF_MODE = "external-file-transfer"
AWAITING_TRANSFER = "awaiting-transfer"
CONNECTOR_SENT = "connector-sent"
KINDLE_DOMAINS = frozenset({"kindle.com", "free.kindle.com"})
SCHEMA_VERSION = 1
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class DeliveryError(RuntimeError):
    """Raised when a local Kindle delivery handoff is invalid."""


@dataclass(frozen=True)
class DeliveryResult:
    workdir: Path
    request_path: Path
    request: dict[str, Any]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_kindle_email(value: str) -> str:
    """Return a normalized Kindle destination, rejecting generic inboxes."""
    if not isinstance(value, str):
        raise DeliveryError("L'indirizzo Kindle deve essere una stringa.")
    recipient = value.strip().lower()
    match = re.fullmatch(r"[^@\s]+@([a-z0-9.-]+)", recipient)

    if match is None or match.group(1) not in KINDLE_DOMAINS:
        raise DeliveryError(
            "L'indirizzo Kindle deve usare esattamente kindle.com "
            "o free.kindle.com."
        )

    return recipient


def request_id_for(recipient: str, attachment_sha256: str) -> str:
    """Build a stable identifier without embedding the recipient in paths."""
    material = f"{recipient}\n{attachment_sha256}".encode("utf-8")
    return "kindle-" + hashlib.sha256(material).hexdigest()[:24]


def expected_attachment_path(workdir: Path, request_id: str) -> Path:
    return workdir / "delivery" / "outbox" / f"{request_id}.epub"


def path_is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def require_nonempty_string(request: dict[str, Any], field: str) -> str:
    value = request.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DeliveryError(
            f"La richiesta di consegna richiede {field} come stringa non vuota."
        )
    return value


def validate_outbox_location(workdir: Path, attachment: Path) -> None:
    """Reject traversal and symlinked outboxes before using an attachment."""
    delivery_dir = workdir / "delivery"
    outbox = delivery_dir / "outbox"
    try:
        resolved_workdir = workdir.resolve(strict=False)
        resolved_delivery = delivery_dir.resolve(strict=False)
        resolved_outbox = outbox.resolve(strict=False)
        resolved_attachment = attachment.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise DeliveryError("Il percorso dell'outbox non è risolvibile.") from error

    if not path_is_within(resolved_delivery, resolved_workdir):
        raise DeliveryError("La directory delivery risolta esce dal workspace.")
    if not path_is_within(resolved_outbox, resolved_delivery):
        raise DeliveryError("L'outbox risolto esce dalla directory delivery.")
    if not path_is_within(resolved_attachment, resolved_outbox):
        raise DeliveryError("Il percorso allegato risolto esce dall'outbox.")


def validate_pending_attachment(request: dict[str, Any], attachment: Path) -> None:
    """Verify the pending attachment without following a symlink."""
    if attachment.is_symlink():
        raise DeliveryError("L'allegato dell'outbox non può essere un symlink.")

    try:
        details = attachment.stat()
    except FileNotFoundError as error:
        raise DeliveryError("L'allegato dell'outbox è assente.") from error
    except OSError as error:
        raise DeliveryError("L'allegato dell'outbox non è leggibile.") from error

    if not stat.S_ISREG(details.st_mode):
        raise DeliveryError("L'allegato dell'outbox non è un file regolare.")
    if details.st_size != request["attachment_bytes"]:
        raise DeliveryError("La dimensione dell'allegato non corrisponde alla richiesta.")

    try:
        actual_hash = sha256_file(attachment)
    except OSError as error:
        raise DeliveryError("Non è possibile calcolare l'hash dell'allegato.") from error
    if actual_hash != request["attachment_sha256"]:
        raise DeliveryError("L'hash dell'allegato non corrisponde alla richiesta.")

    try:
        validate_epub(attachment)
    except (OSError, PublicationError) as error:
        raise DeliveryError("L'allegato dell'outbox non è un EPUB valido.") from error


def validate_delivery_request(
    workdir: Path,
    request: dict[str, Any],
    *,
    verify_pending_attachment: bool,
) -> Path:
    """Validate the durable delivery contract at the filesystem boundary.

    A pending request must retain its verified attachment.  A sent request is
    self-describing and may outlive a deliberately removed outbox file.
    """
    if not isinstance(request, dict):
        raise DeliveryError("La richiesta di consegna non è un oggetto JSON.")

    schema_version = request.get("schema_version")
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise DeliveryError("La richiesta usa una schema_version non supportata.")
    if request.get("provider") != PROVIDER:
        raise DeliveryError("Il provider della richiesta non è gmail-connector.")

    status = request.get("status")
    if not isinstance(status, str) or status not in {"pending", "sent"}:
        raise DeliveryError("La richiesta di consegna ha uno stato non valido.")
    if request.get("handoff_mode") != HANDOFF_MODE:
        raise DeliveryError(
            "La richiesta richiede handoff_mode=external-file-transfer."
        )
    expected_handoff_status = (
        AWAITING_TRANSFER if status == "pending" else CONNECTOR_SENT
    )
    if request.get("handoff_status") != expected_handoff_status:
        raise DeliveryError(
            "handoff_status non è coerente con lo stato della richiesta."
        )

    recipient_value = request.get("recipient")
    if not isinstance(recipient_value, str):
        raise DeliveryError("La richiesta non contiene un destinatario Kindle valido.")
    recipient = validate_kindle_email(recipient_value)
    if recipient != recipient_value:
        raise DeliveryError("Il destinatario Kindle deve essere già normalizzato.")

    attachment_sha256 = request.get("attachment_sha256")
    if (
        not isinstance(attachment_sha256, str)
        or SHA256_PATTERN.fullmatch(attachment_sha256) is None
    ):
        raise DeliveryError("L'hash dell'allegato non è uno SHA-256 valido.")

    request_id = request.get("request_id")
    if not isinstance(request_id, str) or request_id != request_id_for(
        recipient, attachment_sha256
    ):
        raise DeliveryError("Il request_id non corrisponde al contratto della richiesta.")

    require_nonempty_string(request, "subject")
    attachment_bytes = request.get("attachment_bytes")
    if type(attachment_bytes) is not int or attachment_bytes <= 0:
        raise DeliveryError("attachment_bytes deve essere un intero positivo.")
    require_nonempty_string(request, "publication_manifest_path")

    expected_attachment = expected_attachment_path(workdir, request_id)
    attachment_path = request.get("attachment_path")
    if not isinstance(attachment_path, str) or attachment_path != str(
        expected_attachment
    ):
        raise DeliveryError("Il percorso allegato non corrisponde all'outbox previsto.")
    validate_outbox_location(workdir, expected_attachment)

    if status == "sent":
        require_nonempty_string(request, "sent_at")
        require_nonempty_string(request, "receipt")
    elif verify_pending_attachment:
        validate_pending_attachment(request, expected_attachment)

    return expected_attachment


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DeliveryError(f"{label} assente: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeliveryError(f"{label} illeggibile: {path}") from error

    if not isinstance(value, dict):
        raise DeliveryError(f"{label} non contiene un oggetto JSON: {path}")

    return value


def read_delivery_request(request_path: Path) -> dict[str, Any]:
    if request_path.is_symlink():
        raise DeliveryError("La richiesta di consegna non può essere un symlink.")
    return read_json_object(request_path, "Richiesta di consegna")


def validated_publication(workdir: Path) -> tuple[Path, Path, dict[str, Any]]:
    """Locate the current EPUB only when its completed manifest validates it."""
    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    stages = state.get("stages")
    if not isinstance(stages, dict):
        raise DeliveryError("Lo stato della pipeline non contiene stages validi.")
    publish = stages.get("publish")

    if not isinstance(publish, dict) or publish.get("status") != "complete":
        raise DeliveryError("La pubblicazione non risulta completata.")

    outputs = publish.get("outputs")
    if not isinstance(outputs, dict):
        raise DeliveryError("Lo stato publish non contiene gli output validati.")

    manifest_path = Path(str(outputs.get("manifest", ""))).expanduser()
    epub_path = Path(str(outputs.get("epub", ""))).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = workdir / manifest_path
    if not epub_path.is_absolute():
        epub_path = workdir / epub_path

    manifest = read_json_object(manifest_path, "Manifest di pubblicazione")
    files = manifest.get("files")
    epub_record = files.get("epub") if isinstance(files, dict) else None
    if not isinstance(epub_record, dict):
        raise DeliveryError("Il manifest non contiene l'EPUB pubblicato.")
    try:
        if not epub_path.is_file() or epub_path.stat().st_size == 0:
            raise DeliveryError(f"EPUB pubblicato assente o vuoto: {epub_path}")
    except OSError as error:
        raise DeliveryError(f"EPUB pubblicato illeggibile: {epub_path}") from error

    try:
        validate_epub(epub_path)
    except (OSError, PublicationError) as error:
        raise DeliveryError("L'EPUB pubblicato non supera la validazione.") from error

    expected_hash = epub_record.get("sha256")
    try:
        actual_hash = sha256_file(epub_path)
    except OSError as error:
        raise DeliveryError("Non è possibile calcolare l'hash dell'EPUB pubblicato.") from error
    if not isinstance(expected_hash, str) or actual_hash != expected_hash:
        raise DeliveryError("L'hash dell'EPUB non corrisponde al manifest.")

    return epub_path, manifest_path, state


def backup_existing(path: Path) -> Path | None:
    if not path.exists() and not path.is_symlink():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}.backup-{timestamp}{path.suffix}")
    counter = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = path.with_name(
            f"{path.stem}.backup-{timestamp}-{counter}{path.suffix}"
        )
        counter += 1
    path.replace(candidate)
    return candidate


def install_attachment(source: Path, destination: Path, expected_hash: str) -> None:
    """Install an independently copied EPUB after verifying its contents."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        source_details = source.stat()
    except OSError as error:
        raise DeliveryError("L'EPUB pubblicato non è più leggibile.") from error
    if not stat.S_ISREG(source_details.st_mode):
        raise DeliveryError("L'EPUB pubblicato non è un file regolare.")
    source_size = source_details.st_size

    needs_backup = False
    if destination.is_file() and not destination.is_symlink():
        try:
            if (
                destination.stat().st_size == source_size
                and sha256_file(destination) == expected_hash
            ):
                validate_epub(destination)
                return
        except (OSError, PublicationError):
            pass
        needs_backup = True
    elif destination.exists() or destination.is_symlink():
        if destination.is_dir():
            raise DeliveryError("Il percorso dell'allegato è occupato da una directory.")
        needs_backup = True

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as input_stream, os.fdopen(
            descriptor, "wb"
        ) as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        temporary_details = temporary.stat()
        if temporary_details.st_size != source_size:
            raise DeliveryError("La copia locale dell'EPUB non supera la dimensione.")
        if sha256_file(temporary) != expected_hash:
            raise DeliveryError("La copia locale dell'EPUB non supera l'hash.")
        try:
            validate_epub(temporary)
        except PublicationError as error:
            raise DeliveryError("La copia locale non è un EPUB valido.") from error
        if needs_backup:
            backup_existing(destination)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def source_details(workdir: Path, state: dict[str, Any]) -> dict[str, str]:
    metadata = read_json_object(workdir / "metadata.json", "Metadati")
    source_type = metadata.get("source_type") or state.get("source_type")
    details: dict[str, str] = {
        "source_type": source_type if isinstance(source_type, str) else "youtube"
    }
    video = metadata.get("video")
    if isinstance(video, dict) and isinstance(video.get("id"), str):
        details["video_id"] = video["id"]
    elif isinstance(state.get("source_id"), str):
        details["source_id"] = state["source_id"]
    return details


def write_delivery_state(
    workdir: Path,
    request: dict[str, Any],
    complete: bool,
) -> None:
    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    stages = state.setdefault("stages", {})
    delivery: dict[str, Any] = {
        "status": "complete" if complete else "pending",
        "request_id": request["request_id"],
        "recipient": request["recipient"],
        "attachment_sha256": request["attachment_sha256"],
        "handoff_mode": request["handoff_mode"],
        "handoff_status": request["handoff_status"],
        "request_path": str(workdir / "delivery" / REQUEST_FILENAME),
    }
    if complete:
        delivery["completed_at"] = request["sent_at"]
        delivery["receipt"] = request["receipt"]
    stages["delivery"] = delivery
    state["updated_at"] = now_utc()
    atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def request_summary(result: DeliveryResult) -> dict[str, str]:
    request = result.request
    return {
        "request_id": request["request_id"],
        "status": request["status"],
        "handoff_mode": request["handoff_mode"],
        "handoff_status": request["handoff_status"],
        "recipient": request["recipient"],
        "subject": request["subject"],
        "attachment_path": request["attachment_path"],
        "attachment_sha256": request["attachment_sha256"],
        "request_path": str(result.request_path),
    }


def prepare_kindle_delivery(workdir: Path, recipient: str) -> DeliveryResult:
    """Prepare a pending request for transfer to the connector environment."""
    workdir = workdir.expanduser().resolve()
    recipient = validate_kindle_email(recipient)
    epub_path, manifest_path, state = validated_publication(workdir)
    attachment_sha256 = sha256_file(epub_path)
    request_id = request_id_for(recipient, attachment_sha256)
    delivery_dir = workdir / "delivery"
    request_path = delivery_dir / REQUEST_FILENAME

    if request_path.exists() or request_path.is_symlink():
        existing = read_delivery_request(request_path)
        existing_attachment = validate_delivery_request(
            workdir,
            existing,
            verify_pending_attachment=False,
        )
        if existing.get("request_id") == request_id:
            status = existing.get("status")
            if existing.get("recipient") != recipient:
                raise DeliveryError("La richiesta esistente ha un destinatario incoerente.")
            if existing.get("attachment_sha256") != attachment_sha256:
                raise DeliveryError("La richiesta esistente ha un hash incoerente.")
            if existing["attachment_bytes"] != epub_path.stat().st_size:
                raise DeliveryError("La richiesta esistente ha una dimensione incoerente.")
            if status == "pending":
                try:
                    validate_pending_attachment(existing, existing_attachment)
                except DeliveryError:
                    if existing_attachment.is_symlink():
                        raise
                    install_attachment(epub_path, existing_attachment, attachment_sha256)
                    validate_pending_attachment(existing, existing_attachment)
            write_delivery_state(workdir, existing, complete=status == "sent")
            return DeliveryResult(workdir, request_path, existing)
        backup_existing(request_path)

    attachment_path = expected_attachment_path(workdir, request_id)
    validate_outbox_location(workdir, attachment_path)
    install_attachment(epub_path, attachment_path, attachment_sha256)
    created_at = now_utc()
    request: dict[str, Any] = {
        "schema_version": 1,
        "request_id": request_id,
        "created_at": created_at,
        "updated_at": created_at,
        "status": "pending",
        "provider": PROVIDER,
        "handoff_mode": HANDOFF_MODE,
        "handoff_status": AWAITING_TRANSFER,
        "recipient": recipient,
        "subject": "GYTE Study Tools — EPUB per Kindle",
        "attachment_path": str(attachment_path),
        "attachment_sha256": attachment_sha256,
        "attachment_bytes": attachment_path.stat().st_size,
        "publication_manifest_path": str(manifest_path),
    }
    request.update(source_details(workdir, state))
    validate_delivery_request(
        workdir,
        request,
        verify_pending_attachment=True,
    )
    delivery_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(request_path, json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    write_delivery_state(workdir, request, complete=False)
    return DeliveryResult(workdir, request_path, request)


def resolve_workspace(url: str, work_root: Path) -> Path:
    """Resolve an existing private workspace locally, without fetching its URL."""
    root = work_root.expanduser().resolve()
    matches: list[Path] = []
    for metadata_path in root.glob("*/metadata.json"):
        try:
            metadata = read_json_object(metadata_path, "Metadati")
            source = metadata.get("source")
            if isinstance(source, dict) and url in {
                source.get("requested_url"),
                source.get("webpage_url"),
                source.get("canonical_url"),
            }:
                matches.append(metadata_path.parent)
        except DeliveryError:
            continue

    if len(matches) != 1:
        raise DeliveryError(
            "Workspace esistente non risolto in modo univoco dall'URL."
        )
    return matches[0]


def record_kindle_delivery(workdir: Path, receipt: str) -> DeliveryResult:
    """Record a non-empty Gmail connector receipt exactly once."""
    workdir = workdir.expanduser().resolve()
    if not isinstance(receipt, str):
        raise DeliveryError("La ricevuta Gmail connector deve essere una stringa.")
    receipt = receipt.strip()
    if not receipt:
        raise DeliveryError("La ricevuta Gmail connector non può essere vuota.")

    request_path = workdir / "delivery" / REQUEST_FILENAME
    request = read_delivery_request(request_path)
    status = request.get("status")
    validate_delivery_request(
        workdir,
        request,
        verify_pending_attachment=status == "pending",
    )
    if status == "sent":
        if request["receipt"] != receipt:
            raise DeliveryError("La richiesta inviata ha già una ricevuta diversa.")
        write_delivery_state(workdir, request, complete=True)
        return DeliveryResult(workdir, request_path, request)

    request["status"] = "sent"
    request["handoff_status"] = CONNECTOR_SENT
    request["sent_at"] = now_utc()
    request["updated_at"] = request["sent_at"]
    request["receipt"] = receipt
    validate_delivery_request(
        workdir,
        request,
        verify_pending_attachment=False,
    )
    atomic_write_text(request_path, json.dumps(request, ensure_ascii=False, indent=2) + "\n")
    write_delivery_state(workdir, request, complete=True)
    return DeliveryResult(workdir, request_path, request)
