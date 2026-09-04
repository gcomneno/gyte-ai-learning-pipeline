# Source-to-Skill model

GYTE AI Learning Pipeline treats **Source-to-Skill** as a general pattern already present across GiadaWare and LAB workflows rather than as an externally imported idea.

The reusable asset is reviewed and verified knowledge. Human-facing and agent-facing artifacts are separate downstream projections.

## Authority model

```text
source evidence != verified knowledge
verified knowledge != human learning artifact
verified knowledge != agent skill artifact
human learning artifact != agent skill artifact
AI-generated projection != authority
```

The existing rule remains invariant:

```text
AI output != editorial authority
```

## Conceptual flow

```text
source
  -> evidence / acquisition
  -> analysis / principle extraction
  -> source resolution / verification
  -> reviewed knowledge boundary
  -> consumer-specific projection
       -> human-learning artifact
       -> agent-skill artifact
```

The projection boundary must not weaken provenance, verification or authorization semantics.

## Human-learning projection

A human-facing artifact optimizes for learning and transfer. Depending on the subject it may contain:

- conceptual explanation;
- examples and counterexamples;
- progressive exposition;
- exercises or practice;
- misconceptions and limitations;
- review/reflection questions;
- evidence of application or verification.

Pedagogical material that helps a human learner may be intentionally redundant or explanatory in ways that are unnecessary for an agent.

## Agent-skill projection

An agent-facing artifact optimizes for bounded operational reuse. Its semantic contract should include, where justified:

- purpose and activation conditions;
- domain boundaries and explicit non-goals;
- decision rules;
- procedures or workflows;
- patterns and anti-patterns;
- invariants and constraints;
- terminology/glossary;
- examples that improve action selection;
- references/provenance sufficient to inspect the source basis;
- validation criteria;
- modular/selective loading when useful.

An agent skill is not a long-form summary and does not inherit operational permissions from its source.

## Authorization boundary

An agent-skill artifact MUST NOT grant or imply:

- filesystem mutation authority;
- shell/process execution authority;
- network authority;
- Git mutation or merge authority;
- publication authority;
- access to secrets or private source material;
- permission to bypass application authorization;
- self-approval based on model confidence.

The consuming host/application remains responsible for authorization and execution policy.

## Consumer adapter boundary

GYTE core should model the semantic artifact independently from a specific host or package format.

Host-specific packaging belongs in adapters. A future adapter may target an open `SKILL.md`-style format, but the core contract must not depend on Claude Code, Copilot CLI, Amp, one provider/model, one installation directory or one external repository implementation.

## Candidate reviewed-knowledge core

A shared source-independent reviewed knowledge representation should be considered only if a PoV demonstrates that it is useful. Candidate fields include:

- central capability/purpose;
- key principles;
- terminology;
- decision rules;
- procedures;
- patterns;
- anti-patterns;
- constraints/invariants;
- examples;
- limitations;
- source claims and support;
- verification references;
- unresolved questions.

This list is exploratory, not an adopted schema. The PoV must determine the smallest stable semantic core.

## External reference: `virgiliojr94/book-to-skill`

The project is retained as **external architectural/reference evidence**, not as the origin or authority for Source-to-Skill.

Ideas worth comparing during reconnaissance include:

- structured distillation rather than generic summarization;
- explicit decision rules, patterns and anti-patterns;
- compact core skill plus selectively loaded detail;
- document/folder/source-cluster inputs;
- agent-oriented skill packaging;
- generated-skill validation;
- local-first extraction and copyright/provenance boundaries.

Before reusing implementation details, verify current upstream license and architecture and keep concept study distinct from code reuse.

## Relationship to social-source triage

`docs/social-source-triage.md` defines an earlier discovery boundary.

```text
social discovery / triage
  -> promoted candidate source
  -> normal evidence / verification workflow
  -> reviewed knowledge
  -> human or agent projection
```

A social `CANDIDATE` is not reviewed knowledge and cannot skip source resolution.

## Required Proof of Value before broad implementation

Do not implement a generic agent-skill generator until one controlled PoV uses a single already-understood, legitimately usable source to produce two intentionally different candidates from the same reviewed knowledge basis:

### Human projection

A compact artifact with explanation, examples and review/practice material sufficient for a person to learn the concept.

### Agent projection

A compact artifact with operational rules, activation guidance, boundaries, patterns/anti-patterns and modular references sufficient for bounded agent use.

The PoV must record:

- information common to both projections;
- information that must diverge;
- what is lost by mechanically converting one projection into the other;
- whether a stable shared intermediate knowledge model is justified;
- which validations can be deterministic;
- where human editorial judgment remains mandatory.

Only after that review may follow-up implementation issues approve a canonical reviewed-knowledge representation, human projection contract, agent projection adapter, `SKILL.md` packaging or automated validators.

## Copyright and privacy boundary

No projection process may silently publish copyrighted private source material. Rights/licensing decisions remain explicit. Private evidence must not be copied into agent packages merely because the package is locally generated.
