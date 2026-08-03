"""Command-line interface for GYTE Study Tools."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Sequence

from gyte_study_tools import __version__


REQUIRED_COMMANDS: tuple[str, ...] = (
    "python3",
    "gyte-transcript",
    "gyte-reflow-text",
    "yt-dlp",
    "ebook-convert",
    "ebook-meta",
    "pdftotext",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gyte-lesson-kindle",
        description=(
            "Trasforma un video YouTube in materiale di studio, PDF ed EPUB."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL del video YouTube da elaborare.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verifica la disponibilità dei prerequisiti locali.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def check_environment() -> int:
    missing: list[str] = []

    print("===== CONTROLLO AMBIENTE GYTE STUDY TOOLS =====")

    for command in REQUIRED_COMMANDS:
        path = shutil.which(command)

        if path is None:
            missing.append(command)
            print(f"MANCANTE: {command}")
        else:
            print(f"OK: {command} -> {path}")

    print()

    if missing:
        print("ESITO: ambiente incompleto.")
        print("Comandi mancanti: " + ", ".join(missing))
        return 1

    print("ESITO: tutti i prerequisiti sono disponibili.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        return check_environment()

    if args.url:
        print("Pipeline non ancora implementata.")
        print(f"URL ricevuto: {args.url}")
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
