# GYTE AI Learning Pipeline

[English](README.md) | [Italiano](README.it.md)

Companion project for [GYTE](https://github.com/gcomneno/gyte) to transform
videos and transcripts into personal learning materials and formats suitable
for reading on Kindle.

## Goal

Provide a single command:

```text
gyte-lesson-kindle URL_YOUTUBE
```

The intended pipeline is:

```text
YouTube
  → metadata
  → captions or transcription
  → normalization
  → reflow
  → analysis transcript
  → reviewed source lesson
  → explicit review checkpoint
  → PDF and EPUB
  → validation
  → local Kindle request
```

## Status

The assisted pipeline is available for:

1. inspecting YouTube videos;
2. acquiring and normalizing transcripts;
3. preparing analysis material;
4. recording an explicit review checkpoint for an existing private workspace;
5. publishing the checkpointed source lesson as Markdown, HTML, PDF and EPUB;
6. resumable preparation of Kindle delivery;
7. article ingestion.

Drafting of the source lesson remains a controlled editorial step. The review
checkpoint records explicit local acceptance of exact bytes, but it does not
prove human comprehension, factual correctness, source truth, fact-check
completion, AI approval or lesson quality. The Whisper audio fallback is not
implemented yet.

## Responsibilities

This project:

- orchestrates GYTE tools;
- manages directories, metadata and pipeline state;
- validates transcripts and outputs;
- stores prompts and templates;
- generates reading formats.

GYTE continues to handle:

- caption extraction;
- transcript cleaning;
- text reflow.

## Private material

Transcripts, derived material and editorial outputs must not be stored in the
repository.

Default private directory:

```text
~/.local/share/gyte-study-private-material
```

It can be overridden with `--work-root` or by setting
`GYTE_STUDY_WORK_ROOT`.

## Local prerequisites

- Python 3
- `gyte-transcript`
- `gyte-reflow-text`
- `yt-dlp`
- Calibre:
  - `ebook-convert`
  - `ebook-meta`
- `pdftotext`

## Environment check

```bash
bin/gyte-lesson-kindle --check
```

## Intended local installation

```bash
scripts/install-local.sh
```

The installer creates the link:

```text
~/.local/bin/gyte-lesson-kindle
```

The deterministic base pipeline does not require `giadaware-ai`.

The optional `--ai-advisory` operation requires the `giadaware-ai` package to
be importable by the same Python interpreter used by `gyte-lesson-kindle`.
GiadaWare AI is currently distributed separately and is not published to PyPI;
install its built wheel according to the `giadaware-ai` repository installation
instructions. The GYTE installer intentionally does not locate sibling
checkouts, modify `PYTHONPATH` for external packages, or install that optional
dependency automatically.

If `giadaware-ai` or its Ollama composition is not importable,
`--ai-advisory` records an optional `configuration` failure while preserving
the already-successful deterministic preparation.

## Principles

AI capabilities are optional and advisory. AI output is never editorial
authority, and absence or failure of AI must not prevent the deterministic base
pipeline from continuing. AI advisories are explicit operations, not numbered
pipeline stages or pipeline-state authority.

- resumable pipeline;
- no silent overwrites;
- private material separated from code;
- reproducible outputs;
- verifiable stages;
- controlled degradation from captions to Whisper;
- no mandatory dependency on AI services in the assisted version.

## First available stage: inspect

Given a YouTube URL, the command retrieves metadata, identifies the preferred
captions and prepares a resumable private directory:

```bash
gyte-lesson-kindle "https://www.youtube.com/watch?v=VIDEO_ID"
```

Files produced in the private directory:

- `source-url.txt`
- `metadata.json`
- `pipeline-state.json`

This stage does not download captions, audio or video yet.

## Second available stage: prepare

By default, given a URL the command completes both `inspect` and `prepare`:

```bash
gyte-lesson-kindle "https://www.youtube.com/watch?v=VIDEO_ID"
```

The stage produces or resumably adopts:

- `transcript.raw.txt`
- `transcript.normalized.txt`
- `transcript.analysis.txt`
- `transcript.analysis.md`

## Optional AI advisory

The AI advisory runs only when requested explicitly:

```bash
GYTE_AI_MODEL="qwen2.5:1.5b-instruct" \
gyte-lesson-kindle --ai-advisory URL
```

For articles and videos it uses only the current prepared analysis material:

- `transcript.analysis.md` for YouTube;
- `article.analysis.md` for articles.

The canonical input must be a direct workspace child, a regular file, not a
symlink, non-empty and valid UTF-8. Exact input bytes produce SHA-256 and byte
count before strict decoding and before calling the semantic
`analyze_learning_source(text)` capability.

The operation atomically writes:

```text
WORKSPACE/learning-source.analysis.ai.json
```

The filename and semantic artifact identity are distinct. The envelope
contains:

```json
{
  "schema_version": 1,
  "artifact": "learning-source.analysis.ai",
  "authority": "ai-advisory",
  "status": "complete",
  "provenance": {
    "source_type": "youtube|article",
    "canonical_input": "transcript.analysis.md|article.analysis.md",
    "canonical_input_sha256": "...",
    "canonical_input_byte_count": 123
  },
  "payload": {
    "central_thesis": "...",
    "key_concepts": [],
    "source_claims": [],
    "practical_applications": [],
    "limitations": [],
    "review_questions": []
  },
  "failure": null
}
```

Expected optional AI failures use `status: "failed"`, `payload: null` and a
`failure.kind` of `configuration`, `unavailable`, `timeout`,
`invalid-response` or `unsupported`. A failed artifact is never reusable as
success; reusable success requires `status == "complete"` and the same exact
canonical bytes. `--force` regenerates the advisory too. The advisory does not
write `stages.ai-advisory`, mutate `pipeline-state.json`, or create lessons,
publications or delivery requests.

To limit execution to metadata:

```bash
gyte-lesson-kindle --inspect-only URL_YOUTUBE
```

To regenerate preparation outputs:

```bash
gyte-lesson-kindle --force URL_YOUTUBE
```

The Whisper audio fallback is not implemented yet.

## Third available stage: review

Normal URL-only invocation is acquisition and preparation: it resolves or
creates the private workspace, inspects the source when needed, and prepares
video or article analysis material. Downstream review and publication are local
operations against an existing private workspace resolved from the same source
URL; they do not reacquire the source or rerun preparation.

After editorial review, `lesson.md` is the stable source lesson: a
self-contained editorial handoff intended for TritaLeLe. GYTE AI Learning Pipeline does
not invoke TritaLeLe and does not depend on LeLe Manager internals.

The source lesson must satisfy this minimum editorial contract:

- exactly one Markdown H1 title;
- a short purpose or central thesis;
- thematic and reasonably self-contained H2 sections;
- explicit separation between facts, source interpretations and critical assessment;
- reworked concepts and examples without reproducing the full transcript;
- practical applications;
- limitations or unsupported claims;
- review or reflection questions.

`transcript.analysis.md` and `article.analysis.md` remain assisted material for
editorial review; the source lesson is drafted and checked by the editor,
without automatic generation. Record the explicit checkpoint with:

```bash
gyte-lesson-kindle \
  --review-from "/path/to/lesson.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

`--review-from` resolves an existing private workspace locally, requires
`prepare` to be complete, validates the reviewed Markdown including exactly one
H1, writes `reviewed-source-checkpoint.json`, and records `stages.review` in
`pipeline-state.json`. It does not reacquire the source, rerun inspect, rerun
prepare, re-ingest an article, run AI, publish, or mutate evidence and
preparation artifacts.

The checkpoint binds exact reviewed-source bytes, source identity and the
required evidence/preparation artifact bytes: for video, `metadata.json`,
`source-url.txt`, `transcript.raw.txt`, `transcript.normalized.txt`,
`transcript.analysis.txt` and `transcript.analysis.md`; for articles,
`metadata.json`, `source-url.txt`, `article.raw.html`,
`article.extracted.md` and `article.analysis.md`.

The authority ladder remains explicit:

```text
source evidence
!= normalized evidence
!= prepared analysis
!= editorial candidate
!= reviewed source
!= published derivative
```

Prepared or generated material never becomes publication authority implicitly.
The checkpoint proves only that an explicit checkpoint operation occurred over
exact reviewed-source and evidence/preparation bytes. It does not prove causal
editorial lineage from prepared analysis. If the reviewed lesson, source
identity, metadata, source URL, raw or normalized evidence, or prepared
analysis changes after review, publication eligibility becomes stale; rerun
`--review-from` explicitly when the new current material is acceptable.

## Fourth available stage: publish

`--publish-from` is also a downstream local operation against an existing
workspace. It does not reacquire the source, rerun inspect, rerun prepare, or
re-ingest an article. Publish with:

```bash
gyte-lesson-kindle \
  --publish-from "/path/to/lesson.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Publishing requires a current valid explicit review checkpoint and validates
it before publication output mutation. It fails closed if the lesson, source
identity or required evidence/preparation artifact bytes changed after review.
It generates from the same semantic source:

- published Markdown;
- HTML;
- PDF;
- EPUB;
- `publication-manifest.json` with SHA-256 hashes.

Publication manifest schema remains v2. Newly published manifests may include
`review_checkpoint` with `relationship`, `checkpoint_id`,
`checkpoint_sha256` and `created_at`; the SHA is the exact checkpoint identity
validated before publication work. Already-produced valid v2 manifests without
`review_checkpoint` remain valid for Kindle delivery. An old private workspace
without an explicit checkpoint must run `--review-from` once before its next
publication, but that does not invalidate an already-produced valid
manifest-v2 publication for delivery. Delivery accepts both valid v2 forms and
does not reopen `reviewed-source-checkpoint.json` or gain authority over
private transcript, evidence or preparation artifacts.

By default, outputs are saved in:

```text
WORKSPACE_PRIVATO/publication/
```

Previous files with the same name are preserved through timestamped backups.
PDF and EPUB are validated before replacing existing outputs.

## Assisted Kindle delivery

Actual sending is intentionally separated from the local process: the command
contains no credentials and does not access Gmail. The flow is resumable and
has two explicit transitions:

```text
local prepare → transfer/upload attachment → Gmail connector send → local receipt
```

1. Publish and prepare the pending request for a valid Kindle address:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/lesson.md" \
  --kindle-email reader@kindle.com \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

The command verifies the publication manifest, computes SHA-256, creates
`delivery/kindle-delivery-request.json` and displays the absolute path of the
stable attachment in `delivery/outbox/`. That path is local to the workspace
and is not automatically accessible to a Gmail connector running in another
environment. The file must therefore be transferred or uploaded into the
connector environment before sending. The connector may use `attachment_path`
directly only when it shares the same filesystem; otherwise the transfer is
the responsibility of the user or orchestrator. SHA-256 and file size identify
the exact artifact to transfer. The command sends no email.

The attachment is always an independent copy of the published EPUB (never a
hard link), installed atomically after size, SHA-256 and EPUB structure have
been verified.

2. After the connector sends the message, record its receipt (for example a
message ID) without republishing or contacting the network:

```bash
gyte-lesson-kindle \
  --record-kindle-delivery "gmail-message-id" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

The second transition finds the existing workspace from the URL, updates the
request to `sent` and moves `stages.delivery` to `complete`. Recording the same
receipt again is safe; a different receipt is rejected. Only the exact
`kindle.com` and `free.kindle.com` domains are accepted. Before recording the
receipt, the JSON contract and the `pending` attachment are checked again;
after completion the attachment may be removed without invalidating the
coherence of the `sent` request.

The receipt proves that the Gmail connector sent the message, not that Kindle
received, delivered or converted it on the final device.

## Current release

Stable version: `0.4.0`.

The complete assisted pipeline is available:

```text
YouTube URL
  → inspect
  → transcript
  → prepare
  → editorial review
  → review checkpoint
  → publish
  → validated PDF + EPUB
```

Full notes:

- `CHANGELOG.md`
- `docs/release-notes-v0.4.0.md`

## Article input

The command automatically recognizes non-YouTube URLs as articles:

```bash
gyte-lesson-kindle "URL_ARTICOLO"
```

The stage generates:

- `article.raw.html`;
- `article.extracted.md`;
- `article.analysis.md`;
- `metadata.json`;
- `pipeline-state.json`.

The dossier separates journalistic content from detected scientific references
and includes a protocol for distinguishing source claims, primary results,
inferences and facts that still require verification.
