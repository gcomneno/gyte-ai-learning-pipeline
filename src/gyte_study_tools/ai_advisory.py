"""Optional learning-source AI advisory artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text


ADVISORY_FILENAME = "learning-source.analysis.ai.json"
ADVISORY_ARTIFACT = "learning-source.analysis.ai"
ADVISORY_AUTHORITY = "ai-advisory"
SCHEMA_VERSION = 1

CANONICAL_INPUTS = {
    "youtube": "transcript.analysis.md",
    "article": "article.analysis.md",
}

ANALYSIS_FIELDS = (
    "central_thesis",
    "key_concepts",
    "source_claims",
    "practical_applications",
    "limitations",
    "review_questions",
)

STRING_LIST_FIELDS = (
    "key_concepts",
    "practical_applications",
    "limitations",
    "review_questions",
)

CLAIM_FIELDS = ("claim", "support")
SUPPORT_VALUES = {"explicit", "inferred", "unclear"}
FAILURE_KINDS = {
    "configuration",
    "unavailable",
    "timeout",
    "invalid-response",
    "unsupported",
}


class AIAdvisoryError(RuntimeError):
    """Raised for deterministic local or integration contract failures."""


class AIAdvisoryFailure(Exception):
    """Expected optional AI outcome that can be recorded as a failed advisory."""

    def __init__(self, kind: str, message: str) -> None:
        if kind not in FAILURE_KINDS:
            raise ValueError(f"unsupported advisory failure kind: {kind}")
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class AIAdvisoryInput:
    source_type: str
    path: Path
    name: str
    content: str
    sha256: str
    byte_count: int


@dataclass(frozen=True)
class AIAdvisoryResult:
    workdir: Path
    path: Path
    envelope: dict[str, Any]
    reused: bool


Analyzer = Callable[[str], object]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def advisory_path(workdir: Path) -> Path:
    return workdir / ADVISORY_FILENAME


def canonical_input_name(source_type: str) -> str:
    try:
        return CANONICAL_INPUTS[source_type]
    except KeyError as error:
        raise AIAdvisoryError(
            f"Tipo sorgente non supportato per advisory AI: {source_type!r}."
        ) from error


def read_canonical_input(workdir: Path, source_type: str) -> AIAdvisoryInput:
    workdir = workdir.expanduser().resolve()
    name = canonical_input_name(source_type)
    path = workdir / name

    if path.parent != workdir:
        raise AIAdvisoryError("L'input advisory non è un figlio diretto del workspace.")

    if path.is_symlink():
        raise AIAdvisoryError("L'input advisory non può essere un symlink.")

    if not path.exists():
        raise AIAdvisoryError(f"Input advisory mancante: {name}.")

    if not path.is_file():
        raise AIAdvisoryError("L'input advisory deve essere un file regolare.")

    try:
        content = path.read_bytes()
    except OSError as error:
        raise AIAdvisoryError(f"Input advisory illeggibile: {name}.") from error

    if not content:
        raise AIAdvisoryError("L'input advisory è vuoto.")

    digest = sha256_bytes(content)
    byte_count = len(content)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AIAdvisoryError("L'input advisory non è UTF-8 valido.") from error

    if not text.strip():
        raise AIAdvisoryError("L'input advisory è vuoto.")

    return AIAdvisoryInput(
        source_type=source_type,
        path=path,
        name=name,
        content=text,
        sha256=digest,
        byte_count=byte_count,
    )


def provenance_for(input_data: AIAdvisoryInput) -> dict[str, object]:
    return {
        "source_type": input_data.source_type,
        "canonical_input": input_data.name,
        "canonical_input_sha256": input_data.sha256,
        "canonical_input_byte_count": input_data.byte_count,
    }


def envelope_for_success(
    input_data: AIAdvisoryInput,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": ADVISORY_ARTIFACT,
        "authority": ADVISORY_AUTHORITY,
        "status": "complete",
        "created_at": utc_now(),
        "provenance": provenance_for(input_data),
        "payload": payload,
        "failure": None,
    }


def envelope_for_failure(
    input_data: AIAdvisoryInput,
    failure: AIAdvisoryFailure,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": ADVISORY_ARTIFACT,
        "authority": ADVISORY_AUTHORITY,
        "status": "failed",
        "created_at": utc_now(),
        "provenance": provenance_for(input_data),
        "payload": None,
        "failure": {
            "kind": failure.kind,
            "message": failure.message,
        },
    }


def atomic_write_envelope(path: Path, envelope: Mapping[str, object]) -> None:
    atomic_write_text(
        path,
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
    )


def _as_mapping(value: object, fields: Sequence[str], label: str) -> dict[str, object]:
    if isinstance(value, Mapping):
        mapping = dict(value)
    else:
        mapping = {}
        for field in fields:
            if not hasattr(value, field):
                raise AIAdvisoryError(f"{label} non rispetta il contratto pubblico.")
            mapping[field] = getattr(value, field)

    if set(mapping) != set(fields):
        raise AIAdvisoryError(f"{label} contiene campi non conformi al contratto pubblico.")

    return mapping


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AIAdvisoryError(f"{label} deve essere una stringa.")
    return value


def _serialize_string_list(value: object, label: str) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise AIAdvisoryError(f"{label} deve essere una sequenza di stringhe.")

    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_require_string(item, f"{label}[{index}]"))
    return result


def _serialize_support(value: object, label: str) -> str:
    raw = getattr(value, "value", value)
    support = _require_string(raw, label)
    if support not in SUPPORT_VALUES:
        raise AIAdvisoryError(f"{label} non è un valore ClaimSupport valido.")
    return support


def _serialize_claim(value: object, label: str) -> dict[str, str]:
    mapping = _as_mapping(value, CLAIM_FIELDS, label)
    return {
        "claim": _require_string(mapping["claim"], f"{label}.claim"),
        "support": _serialize_support(mapping["support"], f"{label}.support"),
    }


def _serialize_claims(value: object, label: str) -> list[dict[str, str]]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise AIAdvisoryError(f"{label} deve essere una sequenza di SourceClaim.")

    return [
        _serialize_claim(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def serialize_learning_source_analysis(result: object) -> dict[str, object]:
    """Serialize only the public LearningSourceAnalysis consumer contract."""

    mapping = _as_mapping(result, ANALYSIS_FIELDS, "LearningSourceAnalysis")
    payload: dict[str, object] = {
        "central_thesis": _require_string(
            mapping["central_thesis"],
            "central_thesis",
        ),
        "source_claims": _serialize_claims(
            mapping["source_claims"],
            "source_claims",
        ),
    }

    for field in STRING_LIST_FIELDS:
        payload[field] = _serialize_string_list(mapping[field], field)

    return {
        "central_thesis": payload["central_thesis"],
        "key_concepts": payload["key_concepts"],
        "source_claims": payload["source_claims"],
        "practical_applications": payload["practical_applications"],
        "limitations": payload["limitations"],
        "review_questions": payload["review_questions"],
    }


def _valid_success_for_input(
    envelope: Mapping[str, object],
    input_data: AIAdvisoryInput,
) -> bool:
    if envelope.get("status") != "complete":
        return False

    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise AIAdvisoryError("Advisory AI esistente con schema non supportato.")

    if envelope.get("artifact") != ADVISORY_ARTIFACT:
        raise AIAdvisoryError("Advisory AI esistente con identità artefatto non valida.")

    if envelope.get("authority") != ADVISORY_AUTHORITY:
        raise AIAdvisoryError("Advisory AI esistente con authority non valida.")

    if not isinstance(envelope.get("created_at"), str) or not envelope["created_at"]:
        raise AIAdvisoryError("Advisory AI esistente senza created_at valido.")

    provenance = envelope.get("provenance")
    if not isinstance(provenance, Mapping):
        raise AIAdvisoryError("Advisory AI esistente senza provenance valida.")

    if envelope.get("failure") is not None:
        raise AIAdvisoryError("Advisory AI completo contiene failure non nullo.")

    payload = envelope.get("payload")
    if payload is None:
        raise AIAdvisoryError("Advisory AI completo senza payload.")
    serialize_learning_source_analysis(payload)

    return (
        provenance.get("source_type") == input_data.source_type
        and provenance.get("canonical_input") == input_data.name
        and provenance.get("canonical_input_sha256") == input_data.sha256
        and provenance.get("canonical_input_byte_count") == input_data.byte_count
    )


def reusable_success(
    path: Path,
    input_data: AIAdvisoryInput,
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    if path.is_symlink():
        raise AIAdvisoryError("L'artefatto advisory esistente non può essere un symlink.")

    if not path.is_file():
        raise AIAdvisoryError("L'artefatto advisory esistente deve essere un file regolare.")

    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AIAdvisoryError("Artefatto advisory esistente non valido.") from error

    if not isinstance(envelope, dict):
        raise AIAdvisoryError("Artefatto advisory esistente non è un oggetto JSON.")

    if _valid_success_for_input(envelope, input_data):
        return envelope

    return None


def generate_ai_advisory(
    workdir: Path,
    source_type: str,
    *,
    force: bool = False,
    analyzer: Analyzer | None = None,
    analyzer_factory: Callable[[], Analyzer] | None = None,
) -> AIAdvisoryResult:
    workdir = workdir.expanduser().resolve()
    input_data = read_canonical_input(workdir, source_type)
    output_path = advisory_path(workdir)

    if not force:
        existing = reusable_success(output_path, input_data)
        if existing is not None:
            return AIAdvisoryResult(
                workdir=workdir,
                path=output_path,
                envelope=existing,
                reused=True,
            )

    if analyzer is not None and analyzer_factory is not None:
        raise AIAdvisoryError(
            "Specificare analyzer oppure analyzer_factory, non entrambi."
        )

    try:
        if analyzer is not None:
            selected_analyzer = analyzer
        elif analyzer_factory is not None:
            selected_analyzer = analyzer_factory()
        else:
            raise AIAdvisoryError(
                "Nessun analyzer semantico configurato per l'advisory AI."
            )

        raw_result = selected_analyzer(input_data.content)
    except AIAdvisoryFailure as failure:
        envelope = envelope_for_failure(input_data, failure)
        atomic_write_envelope(output_path, envelope)
        return AIAdvisoryResult(
            workdir=workdir,
            path=output_path,
            envelope=dict(envelope),
            reused=False,
        )

    payload = serialize_learning_source_analysis(raw_result)
    envelope = envelope_for_success(input_data, payload)
    atomic_write_envelope(output_path, envelope)

    return AIAdvisoryResult(
        workdir=workdir,
        path=output_path,
        envelope=dict(envelope),
        reused=False,
    )
