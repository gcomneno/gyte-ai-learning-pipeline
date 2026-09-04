"""Consumer contracts and public-safe staging candidate generation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state
from gyte_study_tools.review import ReviewError, validate_review_checkpoint


PUBLIC_STAGING_DIRNAME = "public-staging"
PUBLIC_CANDIDATE_FILENAME = "candidate.md"
PUBLIC_CANDIDATE_RECORD_FILENAME = "candidate.json"
FORBIDDEN_PRIVATE_TOKENS = (
    "transcript.raw.txt",
    "transcript.normalized.txt",
    "transcript.analysis.txt",
    "transcript.analysis.md",
    "article.raw.html",
    "article.extracted.md",
    "article.analysis.md",
    "pipeline-state.json",
    "reviewed-source-checkpoint.json",
    "editorial-candidate.json",
    "fact-check-report.json",
    "Editorial candidate — private",
    "private derived material",
)


class ConsumerContractError(RuntimeError):
    """Raised when a consumer contract or public candidate is unsafe."""


@dataclass(frozen=True)
class ConsumerContract:
    consumer_id: str
    domain: str
    repository: str
    base_branch: str
    output_root: str
    filename_template: str
    local_checkout: str | None


@dataclass(frozen=True)
class PublicCandidateResult:
    workdir: Path
    contract: ConsumerContract
    candidate_path: Path
    record_path: Path
    target_relative_path: str
    candidate_sha256: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or "lesson"


def safe_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsumerContractError(f"{label} deve essere un percorso relativo non vuoto.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ConsumerContractError(f"{label} deve restare relativo e confinato.")
    return path.as_posix()


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConsumerContractError(f"{label} illeggibile: {path}") from error
    if not isinstance(value, dict):
        raise ConsumerContractError(f"{label} non contiene un oggetto JSON.")
    return value


def load_consumer_contract(path: Path) -> ConsumerContract:
    value = read_json_object(path.expanduser(), "Consumer contract")
    if value.get("schema_version") != 1:
        raise ConsumerContractError("Consumer contract schema_version non supportato.")
    required = ("consumer_id", "domain", "repository", "base_branch", "output_root", "filename_template")
    for field in required:
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ConsumerContractError(f"Consumer contract {field} non valido.")
    if re.fullmatch(r"[a-z0-9][a-z0-9-]*", value["consumer_id"]) is None:
        raise ConsumerContractError("consumer_id deve essere uno slug stabile.")
    if re.fullmatch(r"[^/\s]+/[^/\s]+", value["repository"]) is None:
        raise ConsumerContractError("repository deve essere owner/name.")
    output_root = safe_relative_path(value["output_root"], "output_root")
    template = value["filename_template"]
    if "{slug}" not in template:
        raise ConsumerContractError("filename_template deve contenere {slug}.")
    rendered = template.format(slug="fixture")
    safe_relative_path(rendered, "filename_template")
    local_checkout = value.get("local_checkout")
    if local_checkout is not None and (not isinstance(local_checkout, str) or not local_checkout.strip()):
        raise ConsumerContractError("local_checkout deve essere una stringa non vuota quando presente.")
    return ConsumerContract(
        consumer_id=value["consumer_id"],
        domain=value["domain"],
        repository=value["repository"],
        base_branch=value["base_branch"],
        output_root=output_root,
        filename_template=template,
        local_checkout=local_checkout,
    )


def extract_single_h1(markdown: str) -> str:
    headings = [
        match.group(1).strip()
        for line in markdown.splitlines()
        if (match := re.match(r"^#\s+(.+?)\s*$", line))
    ]
    if len(headings) != 1:
        raise ConsumerContractError("Reviewed source deve contenere esattamente un H1.")
    return headings[0]


def h2_outline(markdown: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in markdown.splitlines()
        if (match := re.match(r"^##\s+(.+?)\s*$", line))
    ]


def public_source_metadata(workdir: Path, state: dict[str, Any]) -> dict[str, str]:
    metadata = read_json_object(workdir / "metadata.json", "metadata.json")
    source = metadata.get("source")
    source = source if isinstance(source, dict) else {}
    url = source.get("webpage_url") or source.get("requested_url")
    if not isinstance(url, str) or not url.strip():
        raise ConsumerContractError("Sorgente priva di URL pubblico utilizzabile.")
    if state.get("source_type") == "article":
        article = metadata.get("article")
        title = article.get("title") if isinstance(article, dict) else None
    else:
        video = metadata.get("video")
        title = video.get("title") if isinstance(video, dict) else None
    return {
        "url": url.strip(),
        "title": title.strip() if isinstance(title, str) and title.strip() else "Source",
    }


def fact_check_references(workdir: Path) -> list[str]:
    path = workdir / "fact-check-report.json"
    if not path.is_file() or path.is_symlink():
        return []
    report = read_json_object(path, "Fact-check report")
    if report.get("artifact") != "fact-check-report":
        raise ConsumerContractError("Fact-check report con artifact identity non valida.")
    references: list[str] = []
    claims = report.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            values = claim.get("references")
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip() and value.strip() not in references:
                        references.append(value.strip())
    return references


def render_public_candidate(
    title: str,
    outline: list[str],
    source: dict[str, str],
    references: list[str],
    contract: ConsumerContract,
) -> str:
    lines = [
        f"# {title}",
        "",
        "> Public staging candidate. This is an independently governed downstream artifact, not a copy of private GYTE evidence or the reviewed source lesson.",
        "",
        "## Consumer context",
        "",
        f"- Domain: {contract.domain}",
        f"- Target repository: {contract.repository}",
        "",
        "## Source basis",
        "",
        f"- Source: {source['title']}",
        f"- URL: {source['url']}",
        "",
        "## Editorial outline",
        "",
    ]
    if outline:
        lines.extend(f"- {heading}" for heading in outline)
    else:
        lines.append("- Reconstruct the reviewed knowledge into the consumer's public lesson structure.")
    lines.extend(["", "## Verification references", ""])
    if references:
        lines.extend(f"- {reference}" for reference in references)
    else:
        lines.append("- No public verification references recorded yet.")
    lines.extend(
        [
            "",
            "## Publication boundary",
            "",
            "This staging artifact requires consumer-specific editorial completion and validation before repository materialization. It carries no merge or publication authority.",
            "",
        ]
    )
    return "\n".join(lines)


def boundary_scan(text: str, *, workdir: Path) -> None:
    violations = [token for token in FORBIDDEN_PRIVATE_TOKENS if token in text]
    resolved_workdir = str(workdir.resolve())
    if resolved_workdir and resolved_workdir in text:
        violations.append("private-workspace-path")
    if re.search(r"/(?:home|Users)/[^\s)]+", text):
        violations.append("absolute-user-path")
    if violations:
        raise ConsumerContractError(
            "Public/private boundary violation: " + ", ".join(sorted(set(violations)))
        )


def target_relative_path(contract: ConsumerContract, title: str) -> str:
    filename = contract.filename_template.format(slug=slugify(title))
    filename = safe_relative_path(filename, "rendered filename")
    return (Path(contract.output_root) / filename).as_posix()


def generate_public_candidate(
    workdir: Path,
    reviewed_source_path: Path,
    contract_path: Path,
) -> PublicCandidateResult:
    workdir = workdir.expanduser().resolve()
    reviewed_source_path = reviewed_source_path.expanduser().resolve()
    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    try:
        validated = validate_review_checkpoint(workdir, reviewed_source_path)
    except ReviewError as error:
        raise ConsumerContractError(str(error)) from error

    try:
        reviewed_bytes = reviewed_source_path.read_bytes()
        reviewed_text = reviewed_bytes.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise ConsumerContractError("Reviewed source illeggibile come UTF-8.") from error

    contract = load_consumer_contract(contract_path)
    source = public_source_metadata(workdir, state)
    references = fact_check_references(workdir)
    title = extract_single_h1(reviewed_text)
    outline = h2_outline(reviewed_text)
    candidate = render_public_candidate(title, outline, source, references, contract)
    boundary_scan(candidate, workdir=workdir)

    target = target_relative_path(contract, title)
    staging_dir = workdir / PUBLIC_STAGING_DIRNAME / contract.consumer_id
    candidate_path = staging_dir / PUBLIC_CANDIDATE_FILENAME
    record_path = staging_dir / PUBLIC_CANDIDATE_RECORD_FILENAME
    candidate_bytes = candidate.encode("utf-8")
    candidate_hash = sha256_bytes(candidate_bytes)
    contract_bytes = contract_path.expanduser().read_bytes()
    record = {
        "schema_version": 1,
        "artifact": "public-lesson-candidate",
        "authority": "staging-candidate",
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "consumer": {
            "consumer_id": contract.consumer_id,
            "domain": contract.domain,
            "repository": contract.repository,
            "base_branch": contract.base_branch,
            "target_relative_path": target,
            "contract_sha256": sha256_bytes(contract_bytes),
        },
        "provenance": {
            "reviewed_source_sha256": sha256_bytes(reviewed_bytes),
            "review_checkpoint_sha256": validated.checkpoint_sha256,
            "source_url": source["url"],
            "fact_check_references": references,
        },
        "candidate": candidate_path.name,
        "candidate_sha256": candidate_hash,
        "boundary_scan": "passed",
        "remote_write_authority": False,
    }

    atomic_write_text(candidate_path, candidate)
    atomic_write_text(record_path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")

    state = load_state(state_path)
    stages = state.setdefault("stages", {})
    stages["public_candidate"] = {
        "status": "complete",
        "authority": "staging-candidate",
        "consumer_id": contract.consumer_id,
        "repository": contract.repository,
        "candidate": str(candidate_path.relative_to(workdir)),
        "record": str(record_path.relative_to(workdir)),
        "candidate_sha256": candidate_hash,
        "target_relative_path": target,
        "remote_write_authority": False,
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    return PublicCandidateResult(
        workdir=workdir,
        contract=contract,
        candidate_path=candidate_path,
        record_path=record_path,
        target_relative_path=target,
        candidate_sha256=candidate_hash,
    )
