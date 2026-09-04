# Private editorial candidate

GYTE may derive a private `editorial-candidate.md` from completed prepared analysis. The candidate is an explicit intermediate stage between preparation and a reviewed source lesson.

Canonical invariant:

```text
generated candidate != reviewed source lesson
```

## Artifacts

The operation writes only inside the private workspace:

- `editorial-candidate.md` — generated candidate content;
- `editorial-candidate.json` — machine-verifiable provenance and authority record.

The record declares:

```text
artifact  = editorial-candidate
authority = candidate
status    = complete
```

and binds the exact prepared-analysis filename, SHA-256 and byte count to the exact candidate SHA-256.

## Generation and reuse

Generation requires `prepare` to be `complete`.

The canonical prepared input is:

- `transcript.analysis.md` for video sources;
- `article.analysis.md` for article sources.

If the input identity and existing candidate bytes still match the candidate record, repeated execution reuses the existing candidate. Any input-byte change invalidates reuse. `--force` regenerates the candidate explicitly.

## Promotion boundary

Candidate generation records `stages.candidate`, but this stage has only `authority: candidate`.

It does not create or complete `stages.review`, `stages.publish` or delivery state. Existing publication semantics therefore reject an unreviewed candidate because no current explicit review checkpoint exists.

The candidate may be supplied to the existing review operation as material for explicit editorial acceptance. Only that separate operation turns the exact accepted bytes into a `reviewed-source-snapshot` checkpoint.

```text
prepared analysis
  -> editorial candidate (candidate authority)
  -> explicit human/editorial review
  -> reviewed-source checkpoint (publication authority prerequisite)
```

The review operation is the promotion boundary; generation is not.

## Command

```bash
PYTHONPATH=src python bin/gyte-editorial-candidate /path/to/private/workspace
```

Regenerate explicitly:

```bash
PYTHONPATH=src python bin/gyte-editorial-candidate \
  /path/to/private/workspace \
  --force
```

## Privacy

Prepared analysis and generated candidate material remain private. Neither artifact is intended for Git or automatic publication. Public material still requires the normal review and publication authority chain.
