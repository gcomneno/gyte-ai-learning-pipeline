# Source-to-Skill single-source Proof of Value

## Scope

This Proof of Value exercises the contract from issue #28 without introducing a generic skill generator.

The single source is GYTE's own maintained **approval-gated repository handoff** contract:

- `docs/repository-handoff.md`;
- `src/gyte_study_tools/handoff.py`;
- `tests/test_handoff.py`.

This is an already-understood source from an existing GYTE workflow, maintained in the same repository and legitimately reusable for this controlled comparison.

The reviewed knowledge basis is the contract already established by issue #23:

> a prepared change may be inspected without mutation; mutation requires explicit approval bound to the exact prepared identity; validation precedes remote write; merge authority remains downstream.

This PoV projects that same knowledge into two deliberately different artifacts below.

## Shared reviewed knowledge

The smallest common semantic core observed in this source is:

- **purpose:** automate a downstream repository handoff without collapsing approval boundaries;
- **activation condition:** a validated public candidate and declared consumer contract exist;
- **invariant:** preview/preparation has no consumer-repository mutation authority;
- **decision rule:** approval must bind to the exact prepared plan identity;
- **precondition:** checkout, base branch, base HEAD, repository identity, candidate and contract must still match;
- **procedure:** branch → materialize → boundary scan → validate → commit → push → PR;
- **safety rule:** validation occurs before commit/push;
- **authority rule:** PR creation does not grant merge authority;
- **failure rule:** drift fails closed and pre-push failures retain enough state for safe retry;
- **limitation:** the workflow cannot prove that a downstream reviewer should merge the PR.

This is sufficient for both projections. Explanatory pedagogy and executable-looking operational detail do not belong in the shared core.

## Projection A — human learning artifact

### Approval-gated automation: why preview and mutation must be separate

Automation becomes dangerous when observing a proposed change and authorizing that change are treated as the same event. A safer workflow separates them.

Imagine a tool that wants to place a generated lesson into another repository. During the **preview** phase it may inspect the repository, compute the intended target path, and show the exact diff. It must not create a branch, edit the consumer checkout, push, or open a pull request.

The preview produces a stable identity for the proposed operation. Approval then means: **I approve this exact candidate, against this exact repository state, under this exact contract.**

Before acting, the tool checks those assumptions again. If the repository HEAD changed, the candidate changed, the contract changed, or the checkout points at a different repository, the old approval is stale. The correct response is to stop and prepare a new preview.

Only after the approval still matches may the tool create a branch and materialize the public-safe file. Boundary checks and consumer validation run before commit and push. Opening a pull request is the end of this automation's authority: deciding whether to merge remains a separate downstream responsibility.

### Example

A preview is prepared at base commit `A` for candidate hash `C1`. Before apply, another commit moves the base to `B`.

The old approval must not be reused. Even if the candidate text is unchanged, the approved operation described a different repository state.

### Counterexample

“User approved this kind of change earlier, so pushing the new version is probably fine” is not an approval contract. It substitutes remembered intent for exact authorization.

### Review questions

1. Why is a preview useful even when the generated file itself is already validated?
2. Which identities must be rebound when repository state changes?
3. Why does PR creation not imply merge authority?
4. What is the difference between restartability and silently retrying a remote mutation?

## Projection B — agent skill candidate

### Purpose

Prepare and apply an approval-gated repository handoff while preserving repository, validation, and merge authority boundaries.

### Activate only when

- input is a validated public candidate;
- a declared consumer contract exists;
- the target checkout identity matches the declared repository;
- an explicit handoff operation has been requested.

### Do not

- mutate the consumer checkout during preview;
- infer approval from prior conversation or model confidence;
- reuse approval after plan/candidate/contract/base drift;
- skip boundary or consumer validation;
- push before validation succeeds;
- merge the resulting PR;
- treat source knowledge as permission to use shell, Git, network, or filesystem capabilities that the host has not separately granted.

### Decision rules

1. **No exact approval token → no mutation.**
2. **Any bound identity drift → invalidate approval and re-prepare.**
3. **Repository identity mismatch → stop.**
4. **Private/public boundary failure → stop before commit/push.**
5. **Consumer validation failure → no push.**
6. **PR created → handoff complete; merge remains external.**

### Procedure

1. Validate public candidate identity and consumer contract.
2. Verify clean checkout, declared repository, expected base branch and base HEAD.
3. Produce preview and immutable plan identity without mutating the consumer repository.
4. Require explicit approval of that exact plan identity.
5. Revalidate all bound identities.
6. Create feature branch.
7. Materialize only the contract-allowed target.
8. Run boundary scan and `git diff --check`.
9. Run declared consumer validations.
10. Stage only the declared target and commit.
11. Push the feature branch.
12. Open a PR.
13. Record result with `merge_authority = false`.

### Validation

A compliant implementation must demonstrate:

- preview leaves the consumer target unchanged;
- wrong approval fails before repository mutation;
- wrong repository identity fails closed;
- validation occurs before push;
- failed validation does not push;
- successful handoff records PR identity without merge authority.

## Comparison

### Information common to both

Both projections require:

- exact approval identity;
- revalidation after preview;
- repository/candidate/contract binding;
- validation-before-push;
- explicit merge boundary;
- fail-closed drift semantics.

These fields form a plausible shared intermediate semantic core.

### Information that diverges

The human projection adds:

- motivation and conceptual explanation;
- a worked example and counterexample;
- causal reasoning about stale approval;
- review questions.

The agent projection adds:

- activation conditions;
- imperative decision rules;
- ordered procedure;
- explicit non-goals;
- deterministic validation criteria;
- host-authorization reminder.

### What is lost by mechanical conversion

Converting the human lesson mechanically into an agent skill would leave too much explanatory prose and would not reliably produce activation conditions, stop rules, or validation criteria.

Converting the agent skill mechanically into a human lesson would preserve rules but lose much of the explanation needed to understand *why* the rules exist and how to transfer the principle to a new situation.

Therefore:

```text
human artifact != verbose agent skill
agent skill != compressed human lesson
```

## Intermediate-model decision

**Decision: justify a small shared reviewed-knowledge core, but do not adopt the broad candidate schema from issue #28 yet.**

This PoV needed only:

- purpose;
- activation/preconditions;
- invariants;
- decision rules;
- procedure;
- safety/authority boundaries;
- failure semantics;
- limitations;
- source/provenance.

Terminology, anti-patterns, examples, exercises, glossary and modular references are useful in some projections but are not proven mandatory shared-core fields by this single source.

A follow-up implementation may propose a minimal typed representation around the proven common fields, but this PoV does not approve a universal schema or generator.

## Deterministic vs editorial validation

Deterministic checks can verify:

- required sections/fields exist;
- declared authority is bounded;
- prohibited authority claims are absent;
- provenance points to the reviewed knowledge basis;
- required decision/validation rules are represented;
- package structure conforms to a chosen adapter contract.

Human editorial judgment remains mandatory for:

- whether the extracted principle is actually the important one;
- whether explanations teach the concept accurately;
- whether operational rules preserve the source meaning;
- whether examples are misleading;
- whether omitted nuance changes safe application;
- whether a consumer-specific projection is fit for its intended audience.

## Result

The PoV supports the Source-to-Skill architecture:

```text
reviewed knowledge
  -> human-learning projection
  -> agent-skill projection
```

It also provides evidence that a **small shared semantic core is useful**, while the two downstream artifacts must remain separate first-class projections.

No generic agent-skill generator, host-specific `SKILL.md` adapter, automatic migration, or new execution authority is introduced by this PoV.
