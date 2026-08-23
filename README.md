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
  → PDF and EPUB
  → validation
  → local Kindle request
```

## Status

The assisted pipeline is available for:

1. inspecting YouTube videos;
2. acquiring and normalizing transcripts;
3. preparing analysis material;
4. publishing the validated source lesson as Markdown, HTML, PDF and EPUB;
5. resumable preparation of Kindle delivery;
6. article ingestion.

Review and drafting of the source lesson remain a controlled editorial step.
The Whisper audio fallback is not implemented yet.

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

## Principles

AI capabilities are optional and advisory. AI output is never editorial authority, and absence or failure of AI must not prevent the deterministic base pipeline from continuing.

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

To limit execution to metadata:

```bash
gyte-lesson-kindle --inspect-only URL_YOUTUBE
```

To regenerate preparation outputs:

```bash
gyte-lesson-kindle --force URL_YOUTUBE
```

The Whisper audio fallback is not implemented yet.

## Third available stage: publish

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

`transcript.analysis.md` remains assisted material for editorial review; the
source lesson is drafted and checked by the editor, without automatic
generation. It can then be published with:

```bash
gyte-lesson-kindle \
  --publish-from "/percorso/lesson.md" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

Publishing generates from the same semantic source:

- published Markdown;
- HTML;
- PDF;
- EPUB;
- `publication-manifest.json` with SHA-256 hashes.

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
