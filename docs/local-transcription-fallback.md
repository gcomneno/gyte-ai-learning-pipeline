# Local transcription fallback

GYTE prefers source-provided captions. Local transcription is a fallback only when inspection found no usable caption.

## Selection order

```text
usable source caption
  -> caption acquisition
otherwise
  -> private audio acquisition with yt-dlp
  -> local Whisper transcription
  -> stable private transcript
  -> normal normalization/reflow/preparation
```

The fallback does not turn generated transcription into source-provided evidence. Pipeline provenance records `evidence_origin: local-transcription`; caption-backed runs record `evidence_origin: source-caption`.

## Private artifacts

Fallback artifacts stay inside the private workspace:

- `transcription-source.<ext>` — minimum acquired audio used for local transcription;
- `.whisper-output/` — transient/local Whisper output directory;
- `transcription.local.txt` — stable locally generated transcription evidence;
- the normal `transcript.raw.txt`, normalized and analysis artifacts derived afterwards.

These files must not be committed or published automatically.

## Whisper configuration

The default executable is `whisper` from `PATH` and the default model is `base`.

Optional overrides:

```text
GYTE_WHISPER_COMMAND=/path/to/whisper
GYTE_WHISPER_MODEL=tiny|base|small|...
```

The command override may be an executable path or a command name available on `PATH`.

## Restart and retry semantics

- a completed non-empty `transcription.local.txt` plus its private audio is reused unless `--force` is requested;
- if audio acquisition completed but transcription did not, the existing audio is reused on retry;
- partial `yt-dlp` files are not treated as completed evidence;
- `prepare` is not advanced when local transcription fails;
- completed preparation preserves the original `source_mode`, `evidence_origin` and local-transcription details when stable outputs are reused.

`--force` requests a fresh transcription attempt while still allowing already acquired private audio to be reused.

## Failure contract

Local fallback failures are explicit and classified internally as:

- `configuration` — required executable/path is unavailable;
- `download` — private audio acquisition failed or produced no usable audio;
- `transcription` — Whisper execution failed;
- `output` — Whisper completed without a usable UTF-8 transcript.

These failures surface as preparation errors and do not silently advance later pipeline stages.

## Authority boundary

```text
source caption != locally generated transcription
local transcription != reviewed source lesson
local transcription != factual authority
```

Local Whisper output remains derived evidence that may contain recognition errors. It must pass the same later preparation/editorial boundaries as caption-derived material.
