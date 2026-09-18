# GYTE AI Learning Pipeline v0.5.0 Technical Preview

Version 0.5.0 introduces the first downloadable distribution of GYTE AI
Learning Pipeline.

## Distribution

The release is designed to provide:

- a versioned `.tar.gz` runtime archive;
- a matching `SHA256SUMS` integrity file;
- installation without Git or a persistent repository checkout;
- a versioned user runtime under
  `~/.local/share/gyte-ai-learning-pipeline/0.5.0/`;
- the shipped `gyte-*` commands under `~/.local/bin/`;
- deterministic, byte-reproducible local release construction.

The release builder uses an explicit distribution surface and excludes
repository history, tests, build output, Python caches and private study
material.

## Installation safety

The installer does not use sudo, install external dependencies, overwrite an
existing 0.5.0 runtime, or replace an existing command destination.

GYTE and the publication/acquisition tools remain explicit external
prerequisites.

## Product boundary

This is a CLI-only Technical Preview, not a zero-dependency desktop product.

The release does not add a GUI, bundle heavyweight third-party tools, make
GiadaWare AI mandatory, configure hosted AI silently, or weaken the existing
evidence, review, publication and delivery authority boundaries.

AI remains optional and advisory.

## User and contributor workflows

A user can install from the extracted release archive without Git.

A contributor may continue to work directly from a repository checkout. These
are deliberately separate workflows.
