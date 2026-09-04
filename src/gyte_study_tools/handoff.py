"""Validated consumer-repository handoff up to pull-request creation."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gyte_study_tools.consumers import (
    ConsumerContract,
    ConsumerContractError,
    boundary_scan,
    load_consumer_contract,
)
from gyte_study_tools.inspection import atomic_write_text, load_state


HANDOFF_DIRNAME = "repository-handoff"
PLAN_FILENAME = "plan.json"
PREVIEW_FILENAME = "preview.diff"
RESULT_FILENAME = "result.json"


class HandoffError(RuntimeError):
    """Raised when a repository handoff cannot proceed safely."""

    def __init__(self, message: str, *, step: str = "validation") -> None:
        super().__init__(message)
        self.step = step


@dataclass(frozen=True)
class HandoffPlanResult:
    plan_path: Path
    preview_path: Path
    plan_id: str
    branch: str
    target_path: Path


@dataclass(frozen=True)
class HandoffApplyResult:
    result_path: Path
    branch: str
    commit_sha: str
    pull_request_url: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def run_command(cwd: Path, args: list[str], label: str) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise HandoffError(
            label + (f": {detail}" if detail else ""),
            step=label,
        )
    return completed.stdout.strip()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise HandoffError(f"{label} illeggibile: {path}") from error
    if not isinstance(value, dict):
        raise HandoffError(f"{label} non contiene un oggetto JSON.")
    return value


def resolve_checkout(contract: ConsumerContract, override: Path | None) -> Path:
    value: Path | None = override.expanduser() if override is not None else None
    if value is None and contract.local_checkout is not None:
        value = Path(contract.local_checkout).expanduser()
    if value is None:
        raise HandoffError(
            "Consumer checkout non configurato: usare local_checkout nel contract o --checkout."
        )
    checkout = value.resolve()
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise HandoffError(f"Consumer checkout Git non valido: {checkout}")
    return checkout


def load_valid_public_candidate(
    workdir: Path,
    contract: ConsumerContract,
) -> tuple[Path, Path, dict[str, Any], bytes]:
    state = load_state(workdir / "pipeline-state.json")
    stages = state.get("stages")
    stage = stages.get("public_candidate") if isinstance(stages, dict) else None
    if not isinstance(stage, dict) or stage.get("status") != "complete":
        raise HandoffError("Public candidate validato richiesto prima del repository handoff.")
    if stage.get("consumer_id") != contract.consumer_id:
        raise HandoffError("Consumer contract non corrisponde al public candidate corrente.")
    relative_candidate = stage.get("candidate")
    relative_record = stage.get("record")
    if not isinstance(relative_candidate, str) or not isinstance(relative_record, str):
        raise HandoffError("Public candidate state privo di percorsi validi.")
    for value in (relative_candidate, relative_record):
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise HandoffError("Public candidate state contiene un percorso non confinato.")
    candidate_path = (workdir / relative_candidate).resolve(strict=False)
    record_path = (workdir / relative_record).resolve(strict=False)
    for path, label in ((candidate_path, "candidate"), (record_path, "record")):
        try:
            path.relative_to(workdir)
        except ValueError as error:
            raise HandoffError(f"Public {label} esce dal workspace.") from error
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise HandoffError(f"Public {label} assente, vuoto o symlink.")
    record = read_json(record_path, "Public candidate record")
    consumer = record.get("consumer")
    if (
        record.get("artifact") != "public-lesson-candidate"
        or record.get("authority") != "staging-candidate"
        or record.get("boundary_scan") != "passed"
        or record.get("remote_write_authority") is not False
        or not isinstance(consumer, dict)
        or consumer.get("consumer_id") != contract.consumer_id
        or consumer.get("repository") != contract.repository
        or consumer.get("base_branch") != contract.base_branch
    ):
        raise HandoffError("Public candidate record non coerente con il consumer contract.")
    candidate_bytes = candidate_path.read_bytes()
    digest = sha256_bytes(candidate_bytes)
    if digest != record.get("candidate_sha256") or digest != stage.get("candidate_sha256"):
        raise HandoffError("Public candidate hash mismatch.")
    try:
        candidate_text = candidate_bytes.decode("utf-8")
    except UnicodeError as error:
        raise HandoffError("Public candidate non è UTF-8 valido.") from error
    try:
        boundary_scan(candidate_text, workdir=workdir)
    except ConsumerContractError as error:
        raise HandoffError(str(error)) from error
    return candidate_path, record_path, record, candidate_bytes


def git_repository_identity(checkout: Path) -> tuple[str, str, str]:
    branch = run_command(checkout, ["git", "branch", "--show-current"], "git-current-branch")
    head = run_command(checkout, ["git", "rev-parse", "HEAD"], "git-head")
    status = run_command(checkout, ["git", "status", "--porcelain"], "git-status")
    return branch, head, status


def safe_target(checkout: Path, target_relative: str) -> Path:
    relative = Path(target_relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise HandoffError("Target consumer non confinato.")
    target = (checkout / relative).resolve(strict=False)
    try:
        target.relative_to(checkout.resolve())
    except ValueError as error:
        raise HandoffError("Target consumer esce dal checkout.") from error
    return target


def make_preview(target: Path, candidate_bytes: bytes, checkout: Path) -> str:
    try:
        new_text = candidate_bytes.decode("utf-8").splitlines(keepends=True)
    except UnicodeError as error:
        raise HandoffError("Public candidate non UTF-8.") from error
    if target.exists():
        if target.is_symlink() or not target.is_file():
            raise HandoffError("Target consumer esistente non è un file regolare.")
        old_text = target.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        old_text = []
    relative = target.relative_to(checkout).as_posix()
    return "".join(
        difflib.unified_diff(
            old_text,
            new_text,
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )


def branch_name(contract: ConsumerContract, target_relative: str, candidate_sha: str) -> str:
    stem = re.sub(r"[^a-z0-9-]+", "-", Path(target_relative).stem.lower()).strip("-") or "lesson"
    return f"gyte/{contract.consumer_id}/{stem}-{candidate_sha[:8]}"


def validation_commands(contract_path: Path) -> list[list[str]]:
    raw = read_json(contract_path.expanduser(), "Consumer contract")
    commands = raw.get("validation_commands", [])
    if not isinstance(commands, list):
        raise HandoffError("validation_commands deve essere una lista.")
    parsed: list[list[str]] = []
    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise HandoffError(f"validation_commands[{index}] non valido.")
        parsed.append(command)
    return parsed


def plan_id(material: dict[str, Any]) -> str:
    canonical = json.dumps(material, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "handoff-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_handoff(
    workdir: Path,
    contract_path: Path,
    *,
    checkout_override: Path | None = None,
) -> HandoffPlanResult:
    workdir = workdir.expanduser().resolve()
    contract_path = contract_path.expanduser().resolve()
    contract = load_consumer_contract(contract_path)
    candidate_path, record_path, record, candidate_bytes = load_valid_public_candidate(workdir, contract)
    checkout = resolve_checkout(contract, checkout_override)
    current_branch, current_head, status = git_repository_identity(checkout)
    if status:
        raise HandoffError("Consumer checkout deve essere pulito prima del handoff.")
    if current_branch != contract.base_branch:
        raise HandoffError(
            f"Consumer checkout deve essere su {contract.base_branch}, trovato {current_branch}."
        )
    target_relative = record["consumer"].get("target_relative_path")
    if not isinstance(target_relative, str):
        raise HandoffError("Public candidate record privo di target_relative_path.")
    target = safe_target(checkout, target_relative)
    candidate_sha = sha256_bytes(candidate_bytes)
    branch = branch_name(contract, target_relative, candidate_sha)
    preview = make_preview(target, candidate_bytes, checkout)
    material = {
        "consumer_id": contract.consumer_id,
        "repository": contract.repository,
        "base_branch": contract.base_branch,
        "checkout": str(checkout),
        "base_head": current_head,
        "candidate": str(candidate_path),
        "candidate_sha256": candidate_sha,
        "record": str(record_path),
        "target_relative_path": target_relative,
        "branch": branch,
        "contract": str(contract_path),
        "contract_sha256": sha256_bytes(contract_path.read_bytes()),
    }
    identifier = plan_id(material)
    plan = {
        "schema_version": 1,
        "operation": "repository-handoff",
        "status": "prepared",
        "authority": "publication-approval-required",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": identifier,
        **material,
        "validation_commands": validation_commands(contract_path),
        "remote_write_authority": False,
    }
    handoff_dir = workdir / HANDOFF_DIRNAME / contract.consumer_id
    plan_path = handoff_dir / PLAN_FILENAME
    preview_path = handoff_dir / PREVIEW_FILENAME
    atomic_write_text(plan_path, json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(preview_path, preview)
    return HandoffPlanResult(plan_path, preview_path, identifier, branch, target)


def record_failure(result_path: Path, plan: dict[str, Any], error: HandoffError, progress: dict[str, Any]) -> None:
    payload = {
        "schema_version": 1,
        "operation": "repository-handoff",
        "status": "failed",
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan.get("plan_id"),
        "step": error.step,
        "message": str(error),
        "progress": progress,
        "retry": {
            "branch": plan.get("branch"),
            "base_head": plan.get("base_head"),
            "candidate_sha256": plan.get("candidate_sha256"),
        },
    }
    atomic_write_text(result_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def apply_handoff(plan_path: Path, *, approval: str) -> HandoffApplyResult:
    plan_path = plan_path.expanduser().resolve()
    plan = read_json(plan_path, "Handoff plan")
    if plan.get("schema_version") != 1 or plan.get("status") != "prepared":
        raise HandoffError("Handoff plan non supportato o non prepared.")
    if approval != plan.get("plan_id"):
        raise HandoffError("Publication approval non corrisponde al plan_id corrente.", step="approval")

    workdir = plan_path.parents[2]
    contract_path = Path(plan["contract"])
    contract = load_consumer_contract(contract_path)
    checkout = Path(plan["checkout"]).resolve()
    candidate_path, _, record, candidate_bytes = load_valid_public_candidate(workdir, contract)
    if str(candidate_path) != plan.get("candidate") or sha256_bytes(candidate_bytes) != plan.get("candidate_sha256"):
        raise HandoffError("Public candidate cambiato dopo la preparazione del handoff.", step="preflight")
    if sha256_bytes(contract_path.read_bytes()) != plan.get("contract_sha256"):
        raise HandoffError("Consumer contract cambiato dopo la preparazione del handoff.", step="preflight")
    current_branch, current_head, status = git_repository_identity(checkout)
    if status or current_branch != contract.base_branch or current_head != plan.get("base_head"):
        raise HandoffError("Consumer checkout cambiato dopo la preparazione del handoff.", step="preflight")

    target_relative = plan["target_relative_path"]
    target = safe_target(checkout, target_relative)
    original_bytes = target.read_bytes() if target.is_file() and not target.is_symlink() else None
    result_path = plan_path.with_name(RESULT_FILENAME)
    progress = {
        "branch_created": False,
        "materialized": False,
        "validated": False,
        "committed": False,
        "pushed": False,
        "pr_created": False,
    }

    try:
        run_command(checkout, ["git", "switch", "-c", plan["branch"]], "branch-create")
        progress["branch_created"] = True
        atomic_write_bytes(target, candidate_bytes)
        progress["materialized"] = True
        try:
            boundary_scan(target.read_text(encoding="utf-8"), workdir=workdir)
        except ConsumerContractError as error:
            raise HandoffError(str(error), step="boundary-scan") from error
        run_command(checkout, ["git", "diff", "--check"], "git-diff-check")
        for command in plan.get("validation_commands", []):
            run_command(checkout, command, "consumer-validation")
        progress["validated"] = True
        run_command(checkout, ["git", "add", "--", target_relative], "git-add")
        commit_title = f"docs: add {contract.consumer_id} lesson candidate"
        run_command(checkout, ["git", "commit", "-m", commit_title], "git-commit")
        commit_sha = run_command(checkout, ["git", "rev-parse", "HEAD"], "git-commit-sha")
        progress["committed"] = True
        run_command(checkout, ["git", "push", "-u", "origin", plan["branch"]], "git-push")
        progress["pushed"] = True
        pr_body = (
            "Generated from a validated GYTE public staging candidate.\n\n"
            "The candidate passed the declared consumer validation and private/public boundary checks. "
            "Merge remains an explicit downstream decision."
        )
        pr_url = run_command(
            checkout,
            [
                "gh", "pr", "create",
                "--repo", contract.repository,
                "--base", contract.base_branch,
                "--head", plan["branch"],
                "--title", commit_title,
                "--body", pr_body,
            ],
            "pr-create",
        ).splitlines()[-1]
        progress["pr_created"] = True
    except HandoffError as error:
        record_failure(result_path, plan, error, progress)
        if not progress["pushed"]:
            try:
                if original_bytes is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write_bytes(target, original_bytes)
                if progress["branch_created"]:
                    run_command(checkout, ["git", "reset", "--hard", plan["base_head"]], "rollback-reset")
                    run_command(checkout, ["git", "switch", contract.base_branch], "rollback-switch")
                    run_command(checkout, ["git", "branch", "-D", plan["branch"]], "rollback-branch")
            except Exception:
                pass
        raise

    payload = {
        "schema_version": 1,
        "operation": "repository-handoff",
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "plan_id": plan["plan_id"],
        "repository": contract.repository,
        "base_branch": contract.base_branch,
        "branch": plan["branch"],
        "commit_sha": commit_sha,
        "pull_request_url": pr_url,
        "merge_authority": False,
        "progress": progress,
    }
    atomic_write_text(result_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    state_path = workdir / "pipeline-state.json"
    state = load_state(state_path)
    stages = state.setdefault("stages", {})
    stages["repository_handoff"] = {
        "status": "complete",
        "repository": contract.repository,
        "branch": plan["branch"],
        "commit_sha": commit_sha,
        "pull_request_url": pr_url,
        "merge_authority": False,
    }
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_text(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    return HandoffApplyResult(result_path, plan["branch"], commit_sha, pr_url)
