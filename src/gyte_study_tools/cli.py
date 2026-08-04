"""Command-line interface for GYTE Study Tools."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from gyte_study_tools import __version__
from gyte_study_tools.articles import (
    ArticleError,
    ArticleResult,
    ingest_article,
)
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
from gyte_study_tools.publishing import (
    DEFAULT_AUTHOR,
    PublicationError,
    PublicationResult,
    publish_lesson,
)
from gyte_study_tools.sources import (
    SourceDetectionError,
    detect_source_type,
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
            "Trasforma video YouTube e articoli in materiale di studio, "
            "PDF ed EPUB."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL YouTube o URL di un articolo.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verifica la disponibilità dei prerequisiti locali.",
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Completa soltanto l'ispezione della sorgente.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rigenera gli output preparatori.",
    )
    parser.add_argument(
        "--publish-from",
        type=Path,
        help="Pubblica una Lesson Learned Markdown revisionata.",
    )
    parser.add_argument(
        "--author",
        default=DEFAULT_AUTHOR,
        help=f"Autore degli ebook (default: {DEFAULT_AUTHOR}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory degli output editoriali "
            "(default: WORKSPACE/publication)."
        ),
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
    selected = record["captions"]["selected"]

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
        formats = ", ".join(selected["formats"]) or "non dichiarato"
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
    print(f"Sorgente:        {result.source_transcript_path.name}")
    print(f"Modalità:        {result.source_mode}")
    print(f"Output riusati:  {'sì' if result.reused else 'no'}")
    print(f"Parole raw:      {result.raw_words}")
    print(f"Parole norm.:    {result.normalized_words}")
    print(f"Parole analysis: {result.analysis_words}")
    print()
    print("File da caricare in chat:")
    print(result.analysis_markdown_path)
    print()
    print("ESITO: fase prepare completata.")


def print_article(result: ArticleResult) -> None:
    article = result.record["article"]
    references = result.record["scientific_references"]

    print("===== INGESTIONE ARTICOLO =====")
    print(f"Titolo:       {article['title']}")
    print(
        "Testata/sito: "
        f"{article.get('site_name') or result.record['source']['domain']}"
    )
    print(
        "Autore:       "
        f"{article.get('author') or '<non disponibile>'}"
    )
    print(
        "Pubblicato:   "
        f"{article.get('published_at') or '<non disponibile>'}"
    )
    print(f"Parole:       {result.content_words}")
    print(f"Riferimenti:  {len(references)}")
    print(f"Output riusati: {'sì' if result.reused else 'no'}")
    print()
    print("===== WORKSPACE PRIVATO =====")
    print(f"Directory: {result.workdir}")
    print(f"Metadati:  {result.metadata_path}")
    print(f"HTML raw:  {result.raw_html_path}")
    print(f"Stato:     {result.state_path}")

    if result.analysis_markdown_path is not None:
        print()
        print("File da caricare in chat:")
        print(result.analysis_markdown_path)
        print()
        print("ESITO: articolo estratto e preparato.")
    else:
        print()
        print("ESITO: ispezione articolo completata.")


def print_publication(result: PublicationResult) -> None:
    print()
    print("===== PUBBLICAZIONE LESSON LEARNED =====")
    print(f"Titolo:          {result.title}")
    print(f"Autore:          {result.author}")
    print(f"Parole sorgente: {result.metrics.source_words}")
    print(f"Parole PDF:      {result.metrics.pdf_words}")
    print(f"Parole EPUB:     {result.metrics.epub_words}")
    print(f"Markdown:        {result.canonical_markdown_path}")
    print(f"HTML:            {result.html_path}")
    print(f"PDF:             {result.pdf_path}")
    print(f"EPUB:            {result.epub_path}")
    print(f"Manifest:        {result.manifest_path}")
    print()
    print("ESITO: fase publish completata.")


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
        "analysis_markdown_path": str(
            result.analysis_markdown_path
        ),
        "word_counts": {
            "raw": result.raw_words,
            "normalized": result.normalized_words,
            "analysis": result.analysis_words,
        },
        "source_mode": result.source_mode,
        "reused": result.reused,
    }


def article_to_dict(result: ArticleResult) -> dict[str, object]:
    return {
        "workdir": str(result.workdir),
        "metadata_path": str(result.metadata_path),
        "state_path": str(result.state_path),
        "raw_html_path": str(result.raw_html_path),
        "extracted_markdown_path": (
            str(result.extracted_markdown_path)
            if result.extracted_markdown_path is not None
            else None
        ),
        "analysis_markdown_path": (
            str(result.analysis_markdown_path)
            if result.analysis_markdown_path is not None
            else None
        ),
        "content_words": result.content_words,
        "reused": result.reused,
        "record": result.record,
    }


def publication_to_dict(result: PublicationResult) -> dict[str, object]:
    return {
        "title": result.title,
        "author": result.author,
        "canonical_markdown_path": str(
            result.canonical_markdown_path
        ),
        "html_path": str(result.html_path),
        "pdf_path": str(result.pdf_path),
        "epub_path": str(result.epub_path),
        "manifest_path": str(result.manifest_path),
        "word_counts": {
            "source": result.metrics.source_words,
            "pdf": result.metrics.pdf_words,
            "epub": result.metrics.epub_words,
        },
        "backups": result.backups,
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

    if args.inspect_only and args.publish_from:
        parser.error(
            "--publish-from non è applicabile con --inspect-only."
        )

    if args.output_dir and not args.publish_from:
        parser.error("--output-dir richiede --publish-from.")

    if not args.url:
        parser.print_help()
        return 0

    try:
        source_type = detect_source_type(args.url)
        publication: PublicationResult | None = None

        if source_type == "youtube":
            inspection = inspect_video(args.url, args.work_root)
            preparation = (
                None
                if args.inspect_only
                else prepare_transcript(
                    inspection.workdir,
                    force=args.force,
                )
            )
            article = None
            workdir = inspection.workdir
        else:
            article = ingest_article(
                url=args.url,
                work_root=args.work_root,
                force=args.force,
                inspect_only=args.inspect_only,
            )
            inspection = None
            preparation = None
            workdir = article.workdir

        if args.publish_from is not None:
            publication = publish_lesson(
                workdir=workdir,
                source_path=args.publish_from,
                author=args.author,
                output_dir=args.output_dir,
            )

    except (
        SourceDetectionError,
        InspectionError,
        PreparationError,
        ArticleError,
        PublicationError,
        OSError,
    ) as error:
        print(f"ERRORE: {error}", file=sys.stderr)
        return 1

    if args.json:
        output: dict[str, object] = {
            "source_type": source_type,
        }

        if inspection is not None:
            output["inspection"] = inspection_to_dict(inspection)

        if preparation is not None:
            output["preparation"] = preparation_to_dict(preparation)

        if article is not None:
            output["article"] = article_to_dict(article)

        if publication is not None:
            output["publication"] = publication_to_dict(publication)

        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if inspection is not None:
            print_inspection(inspection)

        if preparation is not None:
            print_preparation(preparation)

        if article is not None:
            print_article(article)

        if publication is not None:
            print_publication(publication)

    return 0


if __name__ == "__main__":
    sys.exit(main())
