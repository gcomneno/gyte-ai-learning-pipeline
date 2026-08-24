"""Explicit reviewed-source editorial checkpoint."""
from __future__ import annotations
import hashlib, json, os, re, tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from gyte_study_tools.inspection import atomic_write_text, load_state
CHECKPOINT_FILENAME = "reviewed-source-checkpoint.json"
CHECKPOINT_OPERATION = "reviewed-source-checkpoint"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CHECKPOINT_ID_PATTERN = re.compile(r"review-[0-9a-f]{64}")
VIDEO_BOUND_ARTIFACTS = (("source-metadata", "metadata.json"), ("source-url", "source-url.txt"), ("source-evidence", "transcript.raw.txt"), ("normalized-evidence", "transcript.normalized.txt"), ("prepared-analysis", "transcript.analysis.txt"), ("prepared-analysis", "transcript.analysis.md"))
ARTICLE_BOUND_ARTIFACTS = (("source-metadata", "metadata.json"), ("source-url", "source-url.txt"), ("source-evidence", "article.raw.html"), ("normalized-evidence", "article.extracted.md"), ("prepared-analysis", "article.analysis.md"))
class ReviewError(RuntimeError): pass
@dataclass(frozen=True)
class ReviewResult:
    workdir: Path; source_path: Path; checkpoint_path: Path; checkpoint_sha256: str; checkpoint: dict[str, Any]

@dataclass(frozen=True)
class ValidatedReviewCheckpoint:
    checkpoint: dict[str, Any]
    checkpoint_sha256: str
def sha256_bytes(content: bytes) -> str: return hashlib.sha256(content).hexdigest()
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
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
def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e: raise ReviewError(f"{label} assente: {path}") from e
    except (OSError, UnicodeError, json.JSONDecodeError) as e: raise ReviewError(f"{label} illeggibile: {path}") from e
    if not isinstance(value, dict): raise ReviewError(f"{label} non contiene un oggetto JSON: {path}")
    return value
def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None: raise ReviewError(f"malformed/unsupported checkpoint: {label} non valido.")
    return value
def extract_single_h1(markdown: str) -> str:
    h1 = [m.group(1).strip() for line in markdown.splitlines() if (m := re.match(r"^#\s+(.+?)\s*$", line))]
    if len(h1) != 1: raise ReviewError("La lezione sorgente revisionata deve contenere esattamente un titolo Markdown H1.")
    return h1[0]
def read_reviewed_source(source_path: Path) -> tuple[bytes, str]:
    if source_path.is_symlink(): raise ReviewError("La lezione sorgente revisionata non può essere un symlink.")
    if not source_path.is_file(): raise ReviewError(f"Lezione sorgente revisionata non trovata: {source_path}")
    data = source_path.read_bytes()
    try: text = data.decode("utf-8")
    except UnicodeError as e: raise ReviewError("La lezione sorgente revisionata deve essere Markdown UTF-8 valido.") from e
    if not data or not text.strip(): raise ReviewError("La lezione sorgente revisionata è vuota.")
    return data, extract_single_h1(text)
def source_identity(workdir: Path, state: dict[str, Any]) -> dict[str, str]:
    meta = read_json_object(workdir / "metadata.json", "metadata.json")
    source_type = meta.get("source_type") if isinstance(meta.get("source_type"), str) else state.get("source_type")
    if source_type == "article":
        sid = state.get("source_id")
        if not isinstance(sid, str) or not sid: raise ReviewError("source identity mismatch: source_id articolo assente.")
        return {"source_type": "article", "source_id_kind": "article-source-id", "source_id": sid}
    video = meta.get("video"); vid = video.get("id") if isinstance(video, dict) else state.get("video_id")
    if not isinstance(vid, str) or not vid: raise ReviewError("source identity mismatch: video_id assente.")
    return {"source_type": "youtube", "source_id_kind": "youtube-video-id", "source_id": vid}
def specs(source_type: str):
    if source_type == "article": return ARTICLE_BOUND_ARTIFACTS
    if source_type == "youtube": return VIDEO_BOUND_ARTIFACTS
    raise ReviewError("source identity mismatch: source_type non supportato.")
def safe_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value: raise ReviewError(f"stale evidence/preparation: {label} non valido.")
    p = Path(value)
    if p.is_absolute() or ".." in p.parts or len(p.parts) != 1 or any(part in {"", "."} for part in p.parts): raise ReviewError(f"stale evidence/preparation: {label} non sicuro.")
    return value
def bound_hash(workdir: Path, name: str) -> str:
    path = workdir / safe_name(name, name)
    if path.is_symlink(): raise ReviewError(f"stale evidence/preparation: {name} non può essere un symlink.")
    if not path.is_file() or path.stat().st_size == 0: raise ReviewError(f"stale evidence/preparation: {name} assente o vuoto.")
    return sha256_file(path)
def current_artifacts(workdir: Path, source_type: str) -> list[dict[str, str]]:
    return [{"role": role, "name": name, "sha256": bound_hash(workdir, name)} for role, name in specs(source_type)]
def checkpoint_id(identity, reviewed, artifacts) -> str:
    material = {"operation": CHECKPOINT_OPERATION, "source_identity": identity, "reviewed_source": {"role": reviewed["role"], "sha256": reviewed["sha256"], "bytes": reviewed["bytes"], "h1": reviewed["h1"]}, "bound_artifacts": artifacts}
    return "review-" + hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def require_prepare_complete(state: dict[str, Any]) -> None:
    stages = state.get("stages"); prepare = stages.get("prepare") if isinstance(stages, dict) else None
    if not isinstance(prepare, dict) or prepare.get("status") != "complete": raise ReviewError("La fase prepare deve essere complete prima della review.")
def restore_checkpoint(
    checkpoint_path: Path,
    previous_bytes: bytes | None,
) -> None:
    if previous_bytes is None:
        checkpoint_path.unlink(missing_ok=True)
        return
    atomic_write_bytes(checkpoint_path, previous_bytes)

def review_lesson(workdir: Path, source_path: Path) -> ReviewResult:
    workdir = workdir.expanduser().resolve()
    source_path = source_path.expanduser().resolve()
    state_path = workdir / "pipeline-state.json"

    state = load_state(state_path)
    require_prepare_complete(state)

    source_bytes, h1 = read_reviewed_source(source_path)
    identity = source_identity(workdir, state)
    artifacts = current_artifacts(workdir, identity["source_type"])
    reviewed = {
        "role": "reviewed-source-snapshot",
        "sha256": sha256_bytes(source_bytes),
        "bytes": len(source_bytes),
        "h1": h1,
    }
    checkpoint = {
        "schema_version": 1,
        "operation": CHECKPOINT_OPERATION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint_id": checkpoint_id(identity, reviewed, artifacts),
        "source_identity": identity,
        "reviewed_source": reviewed,
        "bound_artifacts": artifacts,
    }

    checkpoint_path = workdir / CHECKPOINT_FILENAME

    if checkpoint_path.is_symlink():
        raise ReviewError(
            "malformed/unsupported checkpoint: checkpoint esistente symlink."
        )
    if checkpoint_path.exists() and not checkpoint_path.is_file():
        raise ReviewError(
            "malformed/unsupported checkpoint: checkpoint esistente non regolare."
        )

    previous_checkpoint_bytes = (
        checkpoint_path.read_bytes()
        if checkpoint_path.is_file()
        else None
    )

    atomic_write_text(
        checkpoint_path,
        json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
    )
    checkpoint_sha256 = sha256_file(checkpoint_path)

    try:
        state = load_state(state_path)
        require_prepare_complete(state)
        now = datetime.now(timezone.utc).isoformat()
        stages = state.setdefault("stages", {})
        stages["review"] = {
            "status": "complete",
            "completed_at": now,
            "checkpoint": CHECKPOINT_FILENAME,
            "checkpoint_sha256": checkpoint_sha256,
            "reviewed_source_sha256": reviewed["sha256"],
            "source_type": identity["source_type"],
            "source_id_kind": identity["source_id_kind"],
            "source_id": identity["source_id"],
        }
        state["updated_at"] = now
        atomic_write_text(
            state_path,
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        )
    except Exception:
        restore_checkpoint(checkpoint_path, previous_checkpoint_bytes)
        raise

    return ReviewResult(
        workdir,
        source_path,
        checkpoint_path,
        checkpoint_sha256,
        checkpoint,
    )

def validate_shape(cp: dict[str, Any]) -> None:
    if (
        type(cp.get("schema_version")) is not int
        or cp.get("schema_version") != 1
        or cp.get("operation") != CHECKPOINT_OPERATION
    ):
        raise ReviewError(
            "malformed/unsupported checkpoint: schema o operation non supportati."
        )
    if (
        not isinstance(cp.get("created_at"), str)
        or not isinstance(cp.get("checkpoint_id"), str)
        or CHECKPOINT_ID_PATTERN.fullmatch(cp["checkpoint_id"]) is None
    ):
        raise ReviewError(
            "malformed/unsupported checkpoint: checkpoint_id non valido."
        )
    if (
        not isinstance(cp.get("source_identity"), dict)
        or not isinstance(cp.get("reviewed_source"), dict)
        or not isinstance(cp.get("bound_artifacts"), list)
    ):
        raise ReviewError(
            "malformed/unsupported checkpoint: struttura non valida."
        )
def validate_review_checkpoint(
    workdir: Path,
    source_path: Path,
    *,
    source_bytes: bytes | None = None,
    h1: str | None = None,
) -> ValidatedReviewCheckpoint:
    workdir = workdir.expanduser().resolve(); state = load_state(workdir / "pipeline-state.json"); require_prepare_complete(state); stages = state.get("stages"); review = stages.get("review") if isinstance(stages, dict) else None
    if not isinstance(review, dict) or review.get("status") != "complete": raise ReviewError("review required: eseguire --review-from prima della pubblicazione.")
    if review.get("checkpoint") != CHECKPOINT_FILENAME: raise ReviewError("malformed/unsupported checkpoint: state checkpoint pointer non sicuro.")
    cp_path = workdir / CHECKPOINT_FILENAME
    if cp_path.is_symlink() or not cp_path.is_file(): raise ReviewError("review required: checkpoint assente.")
    try:
        checkpoint_bytes = cp_path.read_bytes()
    except OSError as error:
        raise ReviewError("review required: checkpoint illeggibile.") from error

    cp_hash = sha256_bytes(checkpoint_bytes)
    if review.get("checkpoint_sha256") != cp_hash:
        raise ReviewError(
            "state/checkpoint hash mismatch: checkpoint_sha256 non corrisponde."
        )

    try:
        cp = json.loads(checkpoint_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReviewError(
            "malformed/unsupported checkpoint: checkpoint illeggibile."
        ) from error

    if not isinstance(cp, dict):
        raise ReviewError(
            "malformed/unsupported checkpoint: checkpoint JSON non oggetto."
        )

    validate_shape(cp)
    identity = source_identity(workdir, state)
    if cp["source_identity"] != identity or any(review.get(k) != identity[k] for k in ("source_type", "source_id_kind", "source_id")): raise ReviewError("source identity mismatch: checkpoint non corrisponde alla sorgente corrente.")
    reviewed = cp["reviewed_source"]
    if reviewed.get("role") != "reviewed-source-snapshot": raise ReviewError("malformed/unsupported checkpoint: reviewed_source.role non valido.")
    digest = require_sha256(reviewed.get("sha256"), "reviewed_source.sha256")
    if review.get("reviewed_source_sha256") != digest: raise ReviewError("state/checkpoint hash mismatch: reviewed_source_sha256 non corrisponde.")
    if source_bytes is None or h1 is None: source_bytes, h1 = read_reviewed_source(source_path.expanduser().resolve())
    if sha256_bytes(source_bytes) != digest or len(source_bytes) != reviewed.get("bytes"):
        if h1 != reviewed.get("h1"): raise ReviewError("stale reviewed lesson: H1 revisionato cambiato dopo la review.")
        raise ReviewError("stale reviewed lesson: byte della lezione cambiati dopo la review.")
    if h1 != reviewed.get("h1"): raise ReviewError("stale reviewed lesson: H1 revisionato cambiato dopo la review.")
    actual = cp["bound_artifacts"]; expected = current_artifacts(workdir, identity["source_type"]); expected_keys = [(x["role"], x["name"]) for x in expected]; seen = []
    if len(actual) != len(expected): raise ReviewError("stale evidence/preparation: expected bound artifact set mismatch.")
    for i, art in enumerate(actual):
        if not isinstance(art, dict): raise ReviewError("malformed/unsupported checkpoint: bound artifact non valido.")
        key = (art.get("role"), safe_name(art.get("name"), f"bound_artifacts[{i}].name")); require_sha256(art.get("sha256"), f"bound_artifacts[{i}].sha256")
        if key not in expected_keys or key in seen: raise ReviewError("stale evidence/preparation: expected bound artifact set mismatch.")
        seen.append(key)
        if bound_hash(workdir, art["name"]) != art["sha256"]: raise ReviewError("stale evidence/preparation: artifact bytes changed after review.")
    if seen != expected_keys: raise ReviewError("stale evidence/preparation: expected bound artifact set mismatch.")
    if cp["checkpoint_id"] != checkpoint_id(identity, reviewed, actual): raise ReviewError("malformed/unsupported checkpoint: checkpoint_id non corrisponde.")
    return ValidatedReviewCheckpoint(cp, cp_hash)
