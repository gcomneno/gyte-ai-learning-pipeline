# Social-source triage contract

This document defines the **Book-to-skill** discovery/triage boundary for social posts, reels, infographics and similar low-authority material.

## Core rule

> Extract the useful principle or candidate skill; do not treat the social artifact as authority.

Canonical distinctions:

```text
social discovery signal != authoritative source
candidate skill != verified skill material
AI extraction != editorial authority
```

Promotion means only that the idea is worth entering a normal source-resolution and learning workflow. It does not make the discovery source authoritative.

## State model

A candidate record moves through the following explicit states:

- `CAPTURED` — a URL or source reference has been saved; no quality judgment is implied;
- `TRIAGED` — enough material has been inspected to understand the candidate idea;
- `CANDIDATE` — a potentially useful principle or skill has been extracted;
- `VERIFYING` — stronger, original or authoritative sources are being resolved and checked;
- `PROMOTED` — source-resolution evidence is sufficient for the candidate to enter the normal GYTE learning-source workflow;
- `DISCARDED` — the item is misleading, duplicated, unverifiable, too shallow or not worth further work.

`KEEP` is a human-facing triage decision, not an additional authority state. A `KEEP` item maps to `CANDIDATE` until verification supports `PROMOTED`.

## Minimal candidate record

A triaged item should be representable with a record containing at least:

```json
{
  "schema_version": 1,
  "state": "CAPTURED|TRIAGED|CANDIDATE|VERIFYING|PROMOTED|DISCARDED",
  "capture": {
    "reference": "stable URL or source reference",
    "platform": "facebook|instagram|tiktok|other",
    "title": "optional observed title"
  },
  "observation": {
    "central_idea": "concise derived observation",
    "candidate_principle": "durable principle",
    "candidate_skill": "skill formulation",
    "learning_value": "why it may be worth learning"
  },
  "authority": "discovery-only",
  "source_resolution": {
    "original_or_primary": [],
    "verification_sources": [],
    "status": "unresolved|partial|supported|rejected"
  },
  "decision": "KEEP|PROMOTE|DISCARD",
  "provenance": {
    "derived_from_capture": true
  }
}
```

Engagement metrics and platform-specific mechanics are deliberately excluded unless a demonstrated requirement appears.

## Source-resolution model

A promoted candidate must distinguish:

1. **discovery source** — where the idea was encountered;
2. **original or primary source** — when identifiable;
3. **verification source** — authoritative or high-quality material used to verify/explain the concept;
4. **derived learning artifact** — material later produced through the normal GYTE authority chain.

The discovery source remains in provenance but does not inherit the authority of stronger sources that confirm the same concept.

## Promotion gate

A candidate may become `PROMOTED` only when:

- the candidate principle/skill is formulated independently from promotional wording;
- at least one materially stronger source has been identified;
- the concept is supported well enough to justify normal learning-source preparation;
- unresolved contradictions or scope limits are explicit;
- promotion is an explicit human/editorial decision.

Popularity, visual polish, creator reputation or model confidence are not promotion evidence.

## AI boundary

GiadaWare AI may later assist extraction, classification or source-resolution preparation, but only as advisory output.

AI MUST NOT:

- promote a candidate automatically;
- upgrade a discovery source into authority;
- silently rewrite the captured claim into a stronger one;
- replace source resolution or editorial review.

The existing invariant remains:

```text
AI output != editorial authority
```

## First concrete case

Discovery item: Facebook material from Source Code.dev, observed as an infographic titled **“20 ChatGPT Prompts for Brainstorming”**.

Retained interpretation:

- discovery classification: low-authority candidate source;
- durable principle: structured brainstorming/problem-solving methods are more durable than model-specific prompt recipes;
- candidate skill: select and apply an appropriate brainstorming technique, optionally using an LLM as assistance;
- expected triage decision: `KEEP` / `CANDIDATE`, then `PROMOTE` only after verification against stronger sources.

The social artifact itself does not become authority even if the named brainstorming techniques are later verified independently.

## Manual Proof of Value gate

Before automated social-platform ingestion can be approved, evaluate approximately **10–20 real captured items** manually.

For each item record:

1. the actual observed claim or technique;
2. the durable principle extracted from promotional framing;
3. whether a meaningful candidate skill exists;
4. stronger/original sources to investigate;
5. verification outcome;
6. promote/keep/discard decision;
7. where the original framing was misleading, oversimplified or merely promotional.

Only after this sample demonstrates a recurring, stable structure and meaningful time savings may a separate automation issue be opened.

## Non-goals

This contract does not introduce:

- automatic scraping or ingestion from social platforms;
- access-control or terms-of-service bypass;
- a generic social-media archive;
- engagement-based authority;
- automatic truth/falsehood classification;
- publication of full copyrighted posts, infographics, captions or videos;
- automatic creation of reviewed `lesson.md` artifacts;
- model-specific prompt-library ownership.
