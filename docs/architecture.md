# Initial architecture

[English](architecture.md) | [Italiano](it/architecture.md)

## Boundaries

### GYTE

Provides the general building blocks for obtaining and preparing text:

- `gyte-transcript`
- `gyte-reflow-text`

### GYTE AI Learning Pipeline

Optional AI capabilities may assist analysis, but they do not own pipeline state or editorial authority. Their absence or failure must not invalidate already-valid deterministic stages.

Orchestrates the study and editorial workflow:

- video identification;
- work-directory creation;
- caption selection;
- transcription fallback;
- normalization;
- validation;
- analysis-package creation;
- explicit reviewed-source checkpoint;
- publication of the checkpointed reviewed source lesson;
- Markdown → PDF conversion;
- Markdown → EPUB conversion;
- output validation.

### Private material

Private material is stored outside the repository.

Default directory:

```text
~/.local/share/gyte-study-private-material
```

The path can be overridden through `--work-root` or
`GYTE_STUDY_WORK_ROOT`.

## Intended stages

1. `inspect`
   - metadata retrieval;
   - caption availability check;
   - stable slug creation.

2. `transcribe`
   - prefer `it-orig`;
   - fallback to `it`;
   - future fallback to Whisper.

3. `prepare`
   - preserve the original transcript;
   - UTF-8 and HTML normalization;
   - AI-friendly reflow;
   - word-count verification;
   - generate `transcript.analysis.md`.

4. `review`
   - local downstream operation for an existing private workspace;
   - validates the reviewed Markdown source lesson;
   - requires exactly one H1 and completed preparation;
   - writes `reviewed-source-checkpoint.json` schema v1;
   - records `stages.review` as restart/control state.

5. `compose`
   - assisted version: waits for the reviewed source lesson;
   - future full version: uses a configurable LLM provider.

6. `publish`
   - local downstream operation for an existing private workspace;
   - requires a current valid explicit review checkpoint;
   - validates the checkpoint before publication output mutation;
   - single Markdown source;
   - independent PDF and EPUB generation;
   - coherent metadata;
   - backups of previous outputs.

7. `validate`
   - EPUB ZIP integrity;
   - mimetype verification;
   - recoverable-text check;
   - final summary.

8. `delivery`
   - local **prepare** transition only after `publish` is complete and the
     manifest is valid;
   - verify EPUB hash and size, then create an independent atomic copy in
     `delivery/outbox/` (never a hard link);
   - create `kindle-delivery-request.json` with state `pending`,
     `handoff_mode=external-file-transfer` and
     `handoff_status=awaiting-transfer`;
   - transfer/upload the local attachment into an environment accessible to
     the Gmail connector, then send externally;
   - local **record receipt** transition that stores the receipt and updates
     the state to `complete` with `handoff_status=connector-sent`.

## Resumable state

Each stage must produce a recognizable state file or output.

A new execution must not automatically repeat a stage that is already valid,
unless explicitly requested with options such as:

```text
--force
--from prepare
--rebuild epub
```

## Dependencies

The initial version uses only:

- Python standard library;
- GYTE commands;
- `yt-dlp`;
- Calibre;
- Poppler.

It does not require Pandoc, WeasyPrint or wkhtmltopdf.

## Current implementation

The `inspect` stage is available and:

- queries `yt-dlp` without downloading media;
- collects metadata and caption languages;
- prefers `it-orig`, then `it`;
- distinguishes manual and automatic captions;
- creates a stable private workspace;
- records stage state as JSON.

### Prepare stage

The `prepare` stage:

- reuses an existing caption transcript;
- invokes `gyte-transcript` only when necessary;
- keeps a stable copy of the original text;
- normalizes HTML entities;
- performs AI-friendly reflow;
- verifies that reflow does not lose words;
- generates the Markdown uploaded for editorial review;
- adopts complete existing outputs without rewriting them;
- records the `transcribe` and `prepare` stages in the state file.

### Review stage

The `review` stage is the explicit evidence-to-reviewed-source authority
checkpoint. The authority ladder is intentionally non-collapsing:

```text
source evidence
!= normalized evidence
!= prepared analysis
!= editorial candidate
!= reviewed source
!= published derivative
```

`--review-from LESSON SOURCE_URL` resolves an existing private workspace
locally from `SOURCE_URL`. It does not reacquire the source, rerun inspect,
rerun prepare, re-ingest an article, publish, run AI, or mutate evidence and
preparation artifacts. It requires `prepare` complete, validates the reviewed
Markdown including exactly one H1, writes `reviewed-source-checkpoint.json`
schema v1, and records `stages.review` in `pipeline-state.json`.

`reviewed-source-checkpoint.json` is private authoritative review evidence. It
binds exact reviewed-source bytes, the observed source identity, and exact bytes
of the required evidence/preparation artifacts. For video those artifacts are
`metadata.json`, `source-url.txt`, `transcript.raw.txt`,
`transcript.normalized.txt`, `transcript.analysis.txt` and
`transcript.analysis.md`. For articles they are `metadata.json`,
`source-url.txt`, `article.raw.html`, `article.extracted.md` and
`article.analysis.md`.

`stages.review` is restartability and control metadata: a pointer/hash summary
of the checkpoint, not editorial authority itself. Checkpoint replacement and
state update are fail-safe; a failed state update must not leave state silently
pointing at a different checkpoint.

The checkpoint proves only that an explicit checkpoint operation occurred, the
exact reviewed-source bytes, the source identity observed for that checkpoint,
and the exact bytes of the required evidence/preparation artifacts. It does not
prove human comprehension, factual correctness, source truth, fact-check
completion, AI approval, lesson quality, or causal derivation/editorial lineage
from prepared analysis.

Changing the reviewed lesson, source identity, metadata, source URL, raw or
normalized evidence, or prepared analysis makes the checkpoint stale for
publication. Re-running `--review-from` explicitly restores publication
eligibility only if the new current material is acceptable.

### Publish stage

The `publish` stage:

- accepts a reviewed Markdown source lesson from an existing local workspace;
- does not reacquire the source, rerun inspect, rerun prepare or re-ingest an article;
- requires a current valid explicit review checkpoint before output mutation;
- derives the title from the H1;
- preserves the H1 title without adding labels;
- renders semantic HTML without external Python dependencies;
- generates PDF and EPUB separately through Calibre;
- validates EPUB structure and recoverable text;
- validates recoverable text from the PDF;
- preserves previous outputs with timestamped backups;
- generates `publication-manifest.json` schema v2 with SHA-256 hashes;
- records publication in pipeline state.

An explicit `--output-dir` may place publication outputs outside the workspace.
That directory is publication authority only because `publish_lesson` records
the concrete manifest and EPUB paths in pipeline state.

Publication manifest v2 records byte-level publication provenance and observed source/preparation context only:

- `reviewed_source.sha256` is the exact byte hash of the Markdown source read
  by `publish_lesson`;
- `files.markdown.sha256` is the exact byte hash of the installed publication
  Markdown copy and must equal `reviewed_source.sha256`;
- `files.html`, `files.pdf` and `files.epub` are derived publication
  artifacts with explicit `role` and `derived_from` relationships;
- `source_context.metadata_sha256`, when present, is only the exact byte hash
  of `metadata.json` observed at publication time;
- `source_context.prepared_artifacts[]` records only prepared-analysis
  artifacts observed at publication time and their exact byte hashes.

Issue #17 established byte-level publication provenance and observed
source/preparation context. It did not prove editorial lineage. Issue #18 adds
the explicit review checkpoint that publication must validate before mutating
outputs.

Publication manifest schema remains v2. Newly published manifests may contain
`review_checkpoint` with `relationship`, `checkpoint_id`,
`checkpoint_sha256` and `created_at`. The SHA is the exact checkpoint identity
validated before publication work. Valid schema-v2 manifests without
`review_checkpoint` remain valid legacy publication evidence for Kindle
delivery.

### Delivery stage

Kindle delivery keeps the boundary between the private filesystem and the
external connector explicit. `--kindle-email` can be used together with
`--publish-from`: it sends no email, but prepares a verifiable request
containing recipient, subject, hash, size and EPUB path.

The flow is `local prepare -> transfer/upload attachment -> Gmail connector
send -> local receipt`. The outbox path is local to the workspace and is not
automatically readable by the connector: `attachment_path` can be used
directly only with a shared filesystem; otherwise the user or orchestrator
must transfer the file. SHA-256 and file size identify the artifact to
transfer. The Gmail connector returns a receipt for the Gmail send operation.

`--record-kindle-delivery RECEIPT URL` resolves the workspace from local
metadata and records that receipt atomically. The repository contains no OAuth,
SMTP, token or Gmail configuration.

Delivery accepts only a completed publication whose manifest is validated as
schema v2, including both valid legacy manifests without `review_checkpoint`
and newer manifests with `review_checkpoint`. The manifest EPUB path must agree
with publish state, remain relative inside the publication directory, identify
a non-empty regular EPUB, have valid EPUB structure and match the recorded
SHA-256. Delivery does not reopen `reviewed-source-checkpoint.json`, walk
metadata, transcript, prepared-analysis or arbitrary manifest-mentioned paths,
or gain authority over private evidence/preparation artifacts.

When publication used an external `--output-dir`, delivery may prepare the
Kindle handoff from that state-recorded publication directory. The manifest's
own `files.*.path` values remain relative to `publication-manifest.json` and
cannot grant access to unrelated paths.

The EPUB in the outbox is always a copy with a different inode from the
published artifact: the two versions do not share mutable content. Before a
receipt is recorded, the JSON contract, the outbox-confined path, size,
SHA-256 and EPUB structure of the `pending` request are all checked again. A
`sent` request keeps the same structural fields and the same idempotent
receipt; its attachment may be removed after completion. The receipt does not
prove final Kindle reception, delivery or conversion.

### Article input

HTTP URLs not recognized as YouTube follow a distinct pipeline:

1. download HTML with a declared user agent;
2. read Open Graph and JSON-LD metadata;
3. extract the `post-body` or `entry-content` container;
4. exclude page boilerplate;
5. record scientific references separately;
6. produce `article.analysis.md`;
7. perform later editorial review and shared publication.
