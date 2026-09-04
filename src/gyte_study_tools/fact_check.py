"""Private structured fact-check report generation for editorial review."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state


REPORT_FILENAME = "fact-check-report.json"
EVIDENCE_SCHEMA_VERSION = 1
ALLOWED_STATUSES = {"supported", "unsupported", "disputed", "unresolved"}


class FactCheckError(RuntimeError):
    """Raised when a fact-check report cannot be produced safely."""


@dataclass(frozen=True)
class FactCheckResult:
    workdir: Path
    report_path: Path
    input_path: Path
    input_sha256: str
    claim_count: int
    unresolved_count: int


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def require_prepare_complete(state: dict[str, Any]) -> None:
    stages = state.get("stages")
    prepare = stages.get("prepare") if isinstance(stages, dict) else None
    if not isinstance(prepare, dict) or prepare.get("status") != "complete":
        raise FactCheckError("La fase prepare deve essere complete prima del fact-check report.")


def candidate_if_current(workdir: Path, state: dict[str, Any]) -> Path | None:
    stages = state.get("stages")
    candidate = stages.get("candidate") if isinstance(stages, dict) else None
    if not isinstance(candidate, dict) or candidate.get("status") != "complete":
        return None
    name = candidate.get("candidate")
    expected = candidate.get("candidate_sha256")
    if name != "editorial-candidate.md" or not isinstance(expected, str):
        return None
    path = workdir / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        return None
    if sha256_bytes(path.read_bytes()) != expected:
        return None
    return path


def canonical_input(workdir: Path, state: dict[str, Any]) -> Path:
    candidate = candidate_if_current(workdir, state)
    if candidate is not None:
        return candidate
    name = "article.analysis.md" if state.get("source_type") == "article" else "transcript.analysis.md"
    path = workdir / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise FactCheckError(f"Input fact-check assente, vuoto o non regolare: {path}")
    return path


def claim_sentences(markdown: str) -> list[str]:
    """Extract conservative candidate claims from prose without declaring them true."""
    prose: list[str] = []
    in_fence = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line or line.startswith(("#", ">", "- ", "* ")):
            continue
        prose.append(line)

    text = " ".join(prose)
    candidates = re.split(r"(?<=[.!?])\s+", text)
    claims: list[str] = []
    seen: set[str] = set()
    for sentence in candidates:
        value = re.sub(r"\s+", " ", sentence).strip()
        if len(value.split()) < 5 or value in seen:
            continue
        seen.add(value)
        claims.append(value)
    return claims


def claim_priority(text: str) -> str:
    if re.search(r"\b\d+(?:[.,]\d+)?\b|\b(always|never|must|causes?|proves?|guarantees?)\b", text, re.I):
        return "high"
    if re.search(r"\b(should|likely|typically|usually|can|may)\b", text, re.I):
        return "medium"
    return "medium"


def claim_id(text: str) -> str:
    return "claim-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FactCheckError(f"Evidence file illeggibile: {path}") from error
    if not isinstance(value, dict) or value.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise FactCheckError("Evidence file deve essere un oggetto schema_version=1.")
    claims = value.get("claims")
    if not isinstance(claims, dict):
        raise FactCheckError("Evidence file deve contenere claims come oggetto.")
    return claims


def validated_resolution(value: Any, identifier: str) -> dict[str, Any]:
    if value is None:
        return {
            "status": "unresolved",
            "references": [],
            "editorial_qualification": "External verification still required before editorial approval.",
        }
    if not isinstance(value, dict):
        raise FactCheckError(f"Evidence non valida per {identifier}.")
    status = value.get("status")
    references = value.get("references")
    qualification = value.get("editorial_qualification")
    if status not in ALLOWED_STATUSES:
        raise FactCheckError(f"Status non valido per {identifier}: {status}")
    if not isinstance(references, list) or not all(isinstance(item, str) and item.strip() for item in references):
        raise FactCheckError(f"references non valide per {identifier}.")
    if status != "unresolved" and not references:
        raise FactCheckError(f"{identifier} con status {status} richiede almeno una reference.")
    if not isinstance(qualification, str) or not qualification.strip():
        qualification = (
            "No additional qualification recorded."
            if status == "supported"
            else "Editorial qualification required."
        )
    return {
        "status": status,
        "references": references,
        "editorial_qualification": qualification.strip(),
    }


def generate_fact_check_report(
    workdir: Path,
    *,
    evidence_path: Path | None = None,
) -> FactCheckResult:
    workdir = workdir.expanduser().resolve()
    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    require_prepare_complete(state)

    input_path = canonical_input(workdir, state)
    input_bytes = input_path.read_bytes()
    try:
        markdown = input_bytes.decode("utf-8")
    except UnicodeError as error:
        raise FactCheckError("Input fact-check deve essere Markdown UTF-8 valido.") from error
    input_sha256 = sha256_bytes(input_bytes)
    evidence = load_evidence(evidence_path)

    claims: list[dict[str, Any]] = []
    for text in claim_sentences(markdown):
        identifier = claim_id(text)
        resolution = validated_resolution(evidence.get(identifier), identifier)
        claims.append(
            {
                "id": identifier,
                "claim": text,
                "priority": claim_priority(text),
                **resolution,
            }
        )

    unresolved_count = sum(claim["status"] == "unresolved" for claim in claims)
    report = {
        "schema_version": 1,
        "artifact": "fact-check-report",
        "authority": "fact-check-advisory",
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "input": input_path.name,
            "input_sha256": input_sha256,
            "input_byte_count": len(input_bytes),
        },
        "resolution": {
            "claim_count": len(claims),
            "unresolved_count": unresolved_count,
            "all_resolved": bool(claims) and unresolved_count == 0,
        },
        "claims": claims,
        "authority_boundary": {
            "source_evidence_mutated": False,
            "review_granted": False,
            "publication_granted": False,
        },
    }

    report_path = workdir / REPORT_FILENAME
    atomic_write_text(
        report_path,
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )

    # Completing the report is not editorial approval. Record only advisory state.
    state = load_state(state_path)
    require_prepare_complete(state)
    stages = state.setdefault("stages", {})
    stages["fact_check"] = {
        "status": "complete",
        "authority": "fact-check-advisory",
        "report": REPORT_FILENAME,
        "input_sha256": input_sha256,
        "claim_count": len(claims),
        "unresolved_count": unresolved_count,
        "review_granted": False,
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )

    return FactCheckResult(
        workdir=workdir,
        report_path=report_path,
        input_path=input_path,
        input_sha256=input_sha256,
        claim_count=len(claims),
        unresolved_count=unresolved_count,
    )
