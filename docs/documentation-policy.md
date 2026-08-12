# Documentation language policy

[English](documentation-policy.md) | [Italiano](it/documentation-policy.md)

## Canonical language

English is the canonical and default language for maintained public
documentation. Italian is an officially maintained translation for the
document families listed as bilingual below.

When English and Italian wording diverge, the English document is the source
of truth. A translation must preserve requirements, examples, warnings,
limitations and technical meaning; it must not be a shortened summary.

Commands, CLI options, environment variables, paths, filenames and code
snippets are not translated.

## Naming and navigation

- Root documents use `.it.md` for their Italian mirror.
- Canonical documents under `docs/` are English.
- Maintained Italian translations under `docs/it/` preserve the same filename
  and relative directory structure.
- Every maintained pair starts with visible reciprocal `English` and
  `Italiano` links.
- Internal links should stay in the reader's language when a maintained mirror
  exists. Otherwise they may point to the canonical English source.

## Maintained bilingual set

The initial maintained bilingual set is:

- `README.md` / `README.it.md`;
- `docs/documentation-policy.md` / `docs/it/documentation-policy.md`;
- `docs/architecture.md` / `docs/it/architecture.md`.

Other documents do not automatically acquire a translation obligation.

## Historical and release documentation

`CHANGELOG.md` remains a single release-history file. All content that existed
when this bilingual policy was introduced, including the then-current
`[Unreleased]` section, is grandfathered and remains unchanged in its original
language. The first changelog entry added after the bilingual migration and all
subsequent new entries must use English.

Historical release notes, including `docs/release-notes-v0.4.0.md`, remain in
their original language and do not require maintained mirrors.

Historical or completed design and tracking documents also do not
automatically require translation.

Architecture Decision Records are canonical English technical records and do
not require Italian mirrors unless this policy is explicitly changed.

## Synchronization workflow

A change to a maintained bilingual document must:

1. evaluate whether the Italian mirror requires the same change;
2. update both files in the same change when technical meaning changes;
3. preserve reciprocal language selectors;
4. keep commands, options, environment variables, paths, filenames and code
   snippets unchanged;
5. run the documentation tests.

Run the focused checks with:

```bash
python -m unittest tests.test_documentation
```

The checks verify required pairs, reciprocal language selectors and valid
relative Markdown links. They do not perform machine translation or semantic
comparison; semantic parity remains a reviewer responsibility.

## Non-goals

This policy does not introduce runtime or CLI localization, translation of
prompts or templates, automatic translation, semantic-comparison tooling, a
documentation-site generator, or a translation-management platform. Private
study material remains outside the repository and outside the bilingual
documentation contract.
