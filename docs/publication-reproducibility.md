# Publication reproducibility contract

GYTE distinguishes **byte identity** from **content identity**. Equivalent republishes are compared according to the strongest level the current format/toolchain can support honestly.

## Per-format contract

| Format | Contract | Comparison identity |
| --- | --- | --- |
| Markdown | `byte-reproducible` | exact SHA-256 of bytes |
| HTML | `byte-reproducible` | exact SHA-256 of bytes |
| PDF | `content-reproducible` | SHA-256 of normalized extracted visible text |
| EPUB | `content-reproducible` | SHA-256 of normalized visible XHTML/HTML text |

PDF and EPUB remain protected by the exact byte SHA-256 already stored in `publication-manifest.json`. That hash answers **“are these exact bytes unchanged?”**. It is not, by itself, the cross-run reproducibility identity for formats whose generator may inject timestamps, identifiers or metadata.

Canonical distinction:

```text
manifest files.*.sha256 = byte identity / integrity
reproducibility identity = format-specific comparison identity
byte difference != content difference
content equivalence != permission to ignore integrity failure
```

## Why PDF/EPUB are not claimed byte-reproducible

The Calibre/PDF toolchain may emit generated metadata or container details that vary between equivalent runs. GYTE therefore does not claim byte determinism unless and until that property is demonstrated for the supported toolchain.

The verifier normalizes only the human-visible text needed for the declared content-equivalence contract. It does not weaken normal publication validation: current artifacts must still match their byte hashes in manifest v2 before reproducibility is evaluated.

## Verification

Use the repository verifier against one publication:

```bash
PYTHONPATH=src python bin/gyte-publication-reproducibility \
  /path/to/publication/publication-manifest.json
```

Compare two independently produced publications from the same reviewed source:

```bash
PYTHONPATH=src python bin/gyte-publication-reproducibility \
  /path/to/run-a/publication-manifest.json \
  --compare-with /path/to/run-b/publication-manifest.json
```

Exit semantics:

- `0` — verification passed; if comparing, all formats satisfy their declared reproducibility contract;
- `1` — a manifest/artifact could not be verified safely;
- `2` — both publications were readable but failed the declared cross-run reproducibility comparison.

## Normalization

The normalized content identity uses UTF-8/NFC text, HTML entity decoding, line-ending normalization, whitespace collapsing and removal of empty lines. It intentionally does **not** rewrite words, punctuation or semantic content.

For PDF, `pdftotext -nopgbrk` provides visible text. For EPUB, XHTML/HTML entries are processed in stable sorted archive order and only visible textual content participates in the content identity.

The normalization algorithm is part of the verifier contract and must change only through an explicit compatibility decision. A future algorithm change should use a new report/schema version instead of silently changing the meaning of existing identities.

## Equivalent-input gate

Cross-run comparison is meaningful only for the same exact reviewed-source snapshot. The verifier checks `reviewed_source.sha256` and the published Markdown copy before treating two runs as equivalent input.

A changed reviewed source is **not** a reproducibility failure; it is a different publication input and must be evaluated separately.

## Backups and manifests

Backups and manifest timestamps are operational metadata and are not included in publication-content identity. They must not perturb the reviewed source, generated HTML, or normalized PDF/EPUB content being compared.

The manifest itself is not required to be byte-identical across runs because it records run-specific provenance such as `published_at` and backup paths.

## Toolchain dependency

The declared content contract is intentionally narrower than universal rendering equivalence. PDF text extraction depends on `pdftotext`; PDF/EPUB generation currently depends on the configured publication toolchain. Exact tool versions should be captured when a future release/reproducible-build contract requires version pinning.

## Regression expectations

Tests must preserve these invariants:

- byte differences in PDF/EPUB may still satisfy content reproducibility when normalized visible text is identical;
- a visible content change must fail the relevant normalized identity comparison;
- Markdown/HTML byte changes fail their byte-reproducible contract;
- manifest byte hashes remain mandatory integrity checks and cannot be bypassed by normalized equivalence;
- different reviewed-source bytes cannot be compared as the same publication input.
