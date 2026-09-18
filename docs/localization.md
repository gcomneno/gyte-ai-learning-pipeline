# Localization and translation boundary

## Canonical language

GYTE AI Learning Pipeline uses **English (`en`) as the single canonical source language** for new maintained product semantics, public technical documentation, structured contracts, and stable presentation resources.

A localized representation is derived presentation data. It is never a second authority and cannot change domain meaning.

```text
canonical English meaning
  -> deterministic static localization
  -> optional dynamic translation
  -> localized presentation

localized presentation != authority
```

## Static presentation

Stable UI/CLI strings should use deterministic, version-controlled catalogs or resources. Runtime AI translation is not required for normal fixed help text, labels, validation wording, or menus.

Where a CLI and GUI expose the same capability, language selection is a presentation option only. Both surfaces must preserve identical domain semantics, structured results, validation, authorization, mutations, and exit/status behavior.

The target product-level shape is:

```text
--language en   # default
--language it   # derived presentation
```

GYTE currently has a CLI and no GUI. A GUI language selector is therefore not applicable today. Introducing `--language` is deferred until the maintained CLI message catalog is migrated as one coherent surface; adding a selector that localizes only a subset of messages would violate semantic/presentation parity.

## Dynamic human-readable content

Runtime translation is justified only for genuinely dynamic presentation content that is not itself authoritative evidence, reviewed knowledge, structured state, a validation input, or a mutation instruction.

When runtime translation is justified, consumers depend only on the provider-independent GiadaWare AI Translation capability:

```python
result = ai.translate_text(
    text,
    source_language="English",
    target_language="Italian",
)
```

The semantic contract is `TranslateTextCapability / AICapabilities.translate_text()`, documented by GiadaWare AI in `docs/TRANSLATION-CONTRACT.md`.

GYTE must not depend on Ollama fields, model names, provider SDKs, endpoints, or provider-specific translation envelopes.

Translation must preserve meaning and must not silently summarize, rewrite, enrich, correct domain claims, strengthen/weaken uncertainty, or change authorization semantics.

## Failure and fallback

Translation failure is a presentation failure only:

1. preserve the canonical English content unchanged;
2. visibly fall back to English;
3. do not mutate source content or structured state;
4. do not reinterpret a failed translation as domain failure;
5. do not change exit codes, validation results, authorization, or mutations because translation failed.

## Authoritative and derived artifacts

These remain canonical/authoritative according to their existing contracts and are **not** localized by presentation selection:

- source evidence and provenance;
- prepared analysis identity;
- reviewed-source checkpoints;
- fact-check evidence/status;
- pipeline state;
- publication manifests and hashes;
- consumer contracts;
- handoff plans/approval identities;
- machine-readable structured results.

A translated lesson or other translated editorial artifact requires its own explicit editorial/publication decision; language selection alone cannot create reviewed-source authority.

## Maintained documentation

`README.md` and canonical documents under `docs/` are English sources. Maintained Italian mirrors are derived translations governed by `docs/documentation-policy.md`.

The Italian mirror is maintained for reader convenience, but when wording diverges the English source defines the repository contract.

## Repository-specific exceptions

The following multilingual material may remain intentionally:

- maintained Italian documentation mirrors;
- historical changelog/release/design material retained in its original language;
- upstream/source evidence whose original language is part of provenance;
- private learning material whose language belongs to the source/editorial workflow;
- existing legacy Italian CLI diagnostics/help while the static CLI catalog migration remains incomplete.

The last item is explicit migration debt, not a competing canonical language. New CLI semantics and new stable message resources must be authored canonically in English. A future CLI-localization change should migrate the complete maintained message surface and add `--language` atomically rather than creating mixed partial localization.

## Non-goals

This policy does not:

- make GiadaWare AI mandatory;
- translate evidence or authoritative state in place;
- introduce provider-specific translation dependencies;
- require support for every language;
- delete maintained bilingual documentation immediately;
- grant translated output editorial, publication, execution, Git, filesystem, or network authority.
