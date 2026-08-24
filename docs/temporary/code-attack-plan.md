# Temporary code attack plan

> Status: temporary planning document. This file is non-normative and must not be treated as an architectural contract. Remove or replace it once the tracked work is either completed or promoted into maintained architecture/ADR documentation.

## Purpose

Sequence the next structural work on GYTE AI Learning Pipeline so that each step establishes the semantic boundary required by the next one, while preserving the repository rule that capability is not authority.

Canonical working order:

```text
provenance
  -> editorial authority
  -> GiadaWare AI semantic capability
  -> optional AI advisory integration
  -> editorial candidate
  -> fact-check
  -> consumer/public boundary
  -> repository handoff
  -> acquisition/reproducibility hardening
```

## Operating rule

Every change should answer three questions explicitly:

1. What can this component/stage do?
2. What evidence or input is it derived from?
3. What authority does it possess?

If authority is ambiguous, the change is not ready to merge.

## Wave 1 — semantic foundations

### #17 — Strengthen provenance and publication manifest contracts

Goal: make artifact derivation explicit and machine-verifiable without leaking private material or personal paths.

Expected result:

- precise hash semantics;
- explicit provenance chain from evidence/preparation to reviewed source and publication artifacts;
- authority distinctions retained in manifest/state semantics;
- stale/inconsistent/tampered provenance rejected;
- compatibility/version behavior documented and tested.

### #18 — Formalize the evidence-to-reviewed-source editorial checkpoint

Goal: ensure prepared or generated material can never silently become publication authority.

Key invariant:

```text
evidence != prepared analysis != editorial candidate != reviewed source
```

## Wave 2 — GiadaWare AI semantic capability

Finalize the separate GiadaWare AI contract and, if still justified, implement the learning-source analysis capability there first.

Boundary:

```text
AI processes/proposes
software validates/decides/executes
```

GYTE must not depend on provider/model/prompt details.

## Wave 3 — optional AI advisory integration

### #25 — Integrate GiadaWare AI learning-source analysis as an optional advisory stage

Target flow:

```text
prepared analysis
  -> optional GiadaWare AI
  -> private advisory artifact
```

Required invariants:

- AI disabled/unavailable does not invalidate deterministic preparation;
- AI output cannot set reviewed/publication authority;
- AI artifact provenance belongs to GYTE;
- provider identity does not leak into GYTE domain semantics.

## Wave 4 — editorial automation

### #20 — Private editorial candidate

Invariant:

```text
generated candidate != reviewed lesson
```

### #21 — Structured fact-check report

Invariant:

```text
fact-check completion != editorial approval
```

## Wave 5 — public consumer boundary

### #22 — Consumer contracts and public-safe candidates

Target flow:

```text
reviewed private source
  -> consumer adapter
  -> private staging/public-safe candidate
```

Boundary validation must reject private transcript/analysis material, personal paths, pipeline state, acquired media, secrets and other private artifacts.

## Wave 6 — remote automation

### #23 — Validated repository handoff up to PR creation

Target flow:

```text
approved public candidate
  -> local materialization
  -> validation
  -> explicit diff approval
  -> branch/commit/push/PR
```

No automatic merge authority.

## Wave 7 — hardening

### #14 — Local transcription fallback

May be developed independently where useful, provided provenance clearly distinguishes source captions from local transcription.

### #16 — Reproducible publication semantics

Prefer after provenance semantics are stable so reproducibility can distinguish byte identity, content identity and toolchain-dependent nondeterminism accurately.

## Current execution order

1. **#17 — ACTIVE**
2. #18
3. finalize GiadaWare AI contract
4. GiadaWare AI learning-source capability
5. #25
6. #20
7. #21
8. #22
9. #23
10. #14 where operationally useful
11. #16 after provenance/artifact semantics stabilize

## Removal gate

Delete this file when either:

- the sequence is completed; or
- its durable decisions have been promoted into maintained architecture/ADR/project planning documentation.

Do not retain it indefinitely as a second source of truth.
