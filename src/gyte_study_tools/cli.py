"""Command-line interface for GYTE Study Tools."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from gyte_study_tools import __version__
from gyte_study_tools.inspection import (
    DEFAULT_WORK_ROOT,
    InspectionError,
    InspectionResult,
    inspect_video,
)
from gyte_study_tools.preparation import (
    PreparationError,
    PreparationResult,
    prepare_transcript,
)


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
        "--inspect-only",
        action="store_true",
        help="Completa soltanto la fase di ispezione.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rigenera gli output della fase prepare.",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=DEFAULT_WORK_ROOT,
        help=(
            "Directory radice dei materiali privati "
            f"(default: {DEFAULT_WORK_ROOT})."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Stampa il risultato in JSON.",
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


def print_inspection(result: InspectionResult) -> None:
    record = result.record
    video = record["video"]
    captions = record["captions"]
    selected = captions["selected"]

    print("===== ISPEZIONE VIDEO =====")
    print(f"Titolo:              {video['title']}")
    print(f"Canale:              {video['channel'] or '<non disponibile>'}")
    print(
        "Durata:              "
        f"{video['duration_string'] or video['duration_seconds'] or '<non disponibile>'}"
    )
    print(
        "Data pubblicazione:  "
        f"{video['upload_date'] or '<non disponibile>'}"
    )
    print(f"ID:                  {video['id']}")

    if selected is None:
        print("Caption selezionata: nessuna")
        print("Fallback richiesto:  trascrizione audio")
    else:
        formats = ", ".join(selected["formats"]) or "formato non dichiarato"
        print(
            "Caption selezionata: "
            f"{selected['language']} ({selected['source']}; {formats})"
        )
        print("Fallback richiesto:  no")

    print()
    print("===== WORKSPACE PRIVATO =====")
    print(f"Directory:  {result.workdir}")
    print(f"Metadati:   {result.metadata_path}")
    print(f"Stato:      {result.state_path}")
    print()
    print("ESITO: fase inspect completata.")


def print_preparation(result: PreparationResult) -> None:
    print()
    print("===== PREPARAZIONE TRANSCRIPT =====")
    print(f"Sorgente:       {result.source_transcript_path.name}")
    print(f"Modalità:       {result.source_mode}")
    print(f"Output riusati: {'sì' if result.reused else 'no'}")
    print(f"Parole raw:     {result.raw_words}")
    print(f"Parole norm.:   {result.normalized_words}")
    print(f"Parole analysis:{result.analysis_words}")
    print()
    print("File da caricare in chat:")
    print(result.analysis_markdown_path)
    print()
    print("ESITO: fase prepare completata.")


def inspection_to_dict(result: InspectionResult) -> dict[str, object]:
    return {
        "workdir": str(result.workdir),
        "metadata_path": str(result.metadata_path),
        "state_path": str(result.state_path),
        "record": result.record,
    }


def preparation_to_dict(result: PreparationResult) -> dict[str, object]:
    return {
        "workdir": str(result.workdir),
        "source_transcript_path": str(result.source_transcript_path),
        "raw_path": str(result.raw_path),
        "normalized_path": str(result.normalized_path),
        "analysis_text_path": str(result.analysis_text_path),
        "analysis_markdown_path": str(result.analysis_markdown_path),
        "word_counts": {
            "raw": result.raw_words,
            "normalized": result.normalized_words,
            "analysis": result.analysis_words,
        },
        "source_mode": result.source_mode,
        "reused": result.reused,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        if args.url:
            parser.error("--check non può essere combinato con URL.")
        return check_environment()

    if args.inspect_only and args.force:
        parser.error("--force non è applicabile con --inspect-only.")

    if not args.url:
        parser.print_help()
        return 0

    try:
        inspection = inspect_video(args.url, args.work_root)
        preparation = (
            None
            if args.inspect_only
            else prepare_transcript(
                inspection.workdir,
                force=args.force,
            )
        )
    except (
        InspectionError,
        PreparationError,
        OSError,
    ) as error:
        print(f"ERRORE: {error}", file=sys.stderr)
        return 1

    if args.json:
        output: dict[str, object] = {
            "inspection": inspection_to_dict(inspection),
        }

        if preparation is not None:
            output["preparation"] = preparation_to_dict(preparation)

        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_inspection(inspection)

        if preparation is not None:
            print_preparation(preparation)

    return 0


if __name__ == "__main__":
    sys.exit(main())
