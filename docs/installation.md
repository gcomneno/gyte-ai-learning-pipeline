# Installation and removal

## Support envelope

GYTE AI Learning Pipeline 0.5.0 is a CLI-only Technical Preview intended for
technically curious Linux users.

The downloadable archive provides the GYTE AI Learning Pipeline runtime. It
does not bundle or silently install GYTE, yt-dlp, Calibre, pdftotext,
GiadaWare AI, system packages or hosted AI services.

User installation and contributor checkout are separate workflows. Git is not
required to install the downloadable archive.

## Install from the release archive

Keep the archive and checksum file in the same directory:

```bash
sha256sum -c SHA256SUMS
tar -xzf gyte-ai-learning-pipeline-0.5.0.tar.gz
cd gyte-ai-learning-pipeline-0.5.0
scripts/install-local.sh
```

The installer creates a versioned runtime tree at:

```text
~/.local/share/gyte-ai-learning-pipeline/0.5.0/
```

and exposes the shipped commands under:

```text
~/.local/bin/
```

It fails closed when version 0.5.0 is already installed or when one of the
command destinations already exists. It does not overwrite those paths and
does not provide a force mode.

## Verify

Ensure `~/.local/bin` is on `PATH`.

```bash
gyte-lesson-kindle --version
gyte-lesson-kindle --check
```

`--check` reports the external command prerequisites. It does not install them.

## External prerequisites

The current runtime expects:

- Python 3;
- `gyte-transcript` and `gyte-reflow-text` from the separate GYTE project;
- `yt-dlp`;
- `ebook-convert` and `ebook-meta` from Calibre;
- `pdftotext`.

GiadaWare AI is optional. The deterministic base pipeline does not require it.

## Remove version 0.5.0

Removal is intentionally explicit in this Technical Preview. Before removing
command links, verify that they resolve into the 0.5.0 installation tree.

For each installed `gyte-*` command, inspect it with:

```bash
readlink -f ~/.local/bin/gyte-lesson-kindle
```

Only links belonging to:

```text
~/.local/share/gyte-ai-learning-pipeline/0.5.0/bin/
```

should be removed as part of this installation.

After removing those six command links, remove the versioned runtime directory:

```text
~/.local/share/gyte-ai-learning-pipeline/0.5.0/
```

Private study material is separate and must not be deleted as part of program
removal.

## Contributor setup

Repository contributors may continue to run commands from a checkout and use
`PYTHONPATH=src` where documented. That development workflow is not the user
installation path for the downloadable release.
