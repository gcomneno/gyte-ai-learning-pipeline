# Consumer contracts and public-safe staging

GYTE core does not know one downstream repository layout. A **consumer contract** declares the repository-specific projection boundary while GYTE preserves reviewed-source provenance and the private/public separation.

## Contract v1

```json
{
  "schema_version": 1,
  "consumer_id": "physics-study",
  "domain": "physics",
  "repository": "gcomneno/physics-study",
  "base_branch": "main",
  "output_root": "lessons",
  "filename_template": "{slug}.md"
}
```

`local_checkout` may be supplied when a later repository-handoff operation needs a configured local checkout. It is not required merely to create a private staging candidate.

The repository includes `consumer-contracts/physics-study.json` as the first real acceptance case. Nothing in the core branches on `physics-study` or on the physics domain.

## Required authority

Public-candidate generation requires a current, valid reviewed-source checkpoint for the exact reviewed source bytes. Prepared analysis, editorial candidate state or fact-check completion alone are insufficient.

```text
prepared analysis
  -> editorial candidate
  -> fact-check advisory
  -> explicit reviewed-source checkpoint
  -> consumer projection / public staging candidate
```

## Public-safe projection

The generated staging artifact is intentionally **not a copy of the private reviewed lesson**. It contains:

- reviewed title;
- configured consumer/domain/repository context;
- public source title and URL;
- an editorial outline derived from reviewed H2 headings;
- public verification reference URLs from the fact-check report when available;
- a publication-boundary reminder.

Private explanatory paragraphs, transcripts, prepared analysis and workspace state are not copied into the staging candidate.

The resulting artifact is still only:

```text
artifact  = public-lesson-candidate
authority = staging-candidate
```

It has no remote-write, merge or publication authority.

## Boundary scanner

Before materialization into staging, the generated candidate is scanned for private workspace paths, common private artifact names and private-candidate markers. A violation fails closed before the candidate file is written.

Consumer target paths must remain relative/confined and the configured filename template must contain `{slug}`.

## Provenance

`public-staging/<consumer-id>/candidate.json` binds:

- consumer contract SHA-256;
- exact reviewed-source SHA-256;
- exact review-checkpoint SHA-256;
- public source URL;
- fact-check reference URLs;
- target repository/path;
- exact public-candidate SHA-256;
- successful boundary scan.

## Command

```bash
PYTHONPATH=src python bin/gyte-public-candidate \
  /path/to/private/workspace \
  /path/to/private/workspace/lesson.md \
  consumer-contracts/physics-study.json
```

The command writes only into the GYTE private staging workspace. Repository mutation belongs to the separate handoff contract.
