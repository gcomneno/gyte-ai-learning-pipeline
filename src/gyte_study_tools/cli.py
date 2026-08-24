"""Command-line interface for GYTE AI Learning Pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from gyte_study_tools.ai_advisory import (
    AIAdvisoryError,
    AIAdvisoryResult,
    generate_ai_advisory,
)
from gyte_study_tools import __version__
from gyte_study_tools.articles import (
    ArticleError,
    ArticleResult,
    ingest_article,
)
from gyte_study_tools.delivery import (
    DeliveryError,
    DeliveryResult,
    prepare_kindle_delivery,
    record_kindle_delivery,
    request_summary,
    resolve_workspace,
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
from gyte_study_tools.review import (
    ReviewError,
    ReviewResult,
    review_lesson,
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
        "--ai-advisory",
        action="store_true",
        help="Genera o riusa un advisory AI opzionale dal materiale di analisi preparato.",
    )
    parser.add_argument(
        "--review-from",
        type=Path,
        help="Registra il checkpoint editoriale esplicito per una lezione sorgente Markdown revisionata.",
    )
    parser.add_argument(
        "--publish-from",
        type=Path,
        help="Pubblica una lezione sorgente Markdown revisionata già passata da --review-from.",
    )
    parser.add_argument(
        "--kindle-email",
        help=(
            "Prepara una richiesta pending per un indirizzo "
            "@kindle.com o @free.kindle.com dopo --publish-from."
        ),
    )
    parser.add_argument(
        "--record-kindle-delivery",
        metavar="RECEIPT",
        help=(
            "Registra localmente la ricevuta del Gmail connector per "
            "l'URL e il workspace esistenti."
        ),
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

    print("===== CONTROLLO AMBIENTE GYTE AI LEARNING PIPELINE =====")

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


def print_ai_advisory(result: AIAdvisoryResult) -> None:
    envelope = result.envelope
    print()
    print("===== ADVISORY AI =====")
    print(f"Artefatto: {envelope['artifact']}")
    print(f"Stato:     {envelope['status']}")
    print(f"File:      {result.path}")
    print(f"Riusato:   {'sì' if result.reused else 'no'}")

    failure = envelope.get("failure")
    if isinstance(failure, dict):
        print(f"Failure:   {failure['kind']}: {failure['message']}")
        print("ESITO: advisory AI opzionale fallito; preparazione deterministica preservata.")
    else:
        print("ESITO: advisory AI completato.")


def print_review(result: ReviewResult) -> None:
    print()
    print("===== CHECKPOINT EDITORIALE =====")
    print(f"Checkpoint: {result.checkpoint_path}")
    print(f"SHA-256:    {result.checkpoint_sha256}")
    print(f"Sorgente:   {result.checkpoint['source_identity']['source_type']}")
    print(f"ID:         {result.checkpoint['source_identity']['source_id']}")
    print()
    print("ESITO: fase review completata; nessuna pubblicazione eseguita.")


def print_publication(result: PublicationResult) -> None:
    print()
    print("===== PUBBLICAZIONE LEZIONE SORGENTE =====")
    print(f"Titolo:          {result.title}")
    print(f"Autore:          {result.author}")
    print(f"Parole sorgente: {result.metrics.source_words}")
    print(f"Parole PDF:      {result.metrics.pdf_words}")
    print(f"Parole EPUB:     {result.metrics.epub_words}")
    print(f"Markdown:        {result.markdown_path}")
    print(f"HTML:            {result.html_path}")
    print(f"PDF:             {result.pdf_path}")
    print(f"EPUB:            {result.epub_path}")
    print(f"Manifest:        {result.manifest_path}")
    print()
    print("ESITO: fase publish completata.")


def print_delivery(result: DeliveryResult) -> None:
    request = result.request
    heading = (
        "===== RICEVUTA CONSEGNA KINDLE ====="
        if request["status"] == "sent"
        else "===== RICHIESTA CONSEGNA KINDLE ====="
    )
    print()
    print(heading)
    print(f"Stato:       {request['status']}")
    print(f"Handoff:     {request['handoff_mode']} / {request['handoff_status']}")
    print(f"Richiesta:   {request['request_id']}")
    print(f"Destinatario: {request['recipient']}")
    print(f"Oggetto:     {request['subject']}")
    print(f"Allegato:    {request['attachment_path']}")
    print(f"Richiesta JSON: {result.request_path}")
    if request["status"] == "pending":
        print(
            "Azione esterna: trasferire o caricare l'EPUB nell'ambiente "
            "accessibile al Gmail connector, quindi inviarlo e registrare la ricevuta."
        )
        print("Il percorso mostrato è locale al workspace e non è automaticamente leggibile dal connector.")
    else:
        print(f"Ricevuta:    {request['receipt']}")
        print("ESITO: invio Gmail registrato; non attesta la consegna o conversione su Kindle.")


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


def ai_advisory_to_dict(result: AIAdvisoryResult) -> dict[str, object]:
    return {
        "path": str(result.path),
        "reused": result.reused,
        "envelope": result.envelope,
    }


def create_ai_analyzer():
    from gyte_study_tools.ai_composition import create_learning_source_analyzer

    return create_learning_source_analyzer()


def review_to_dict(result: ReviewResult) -> dict[str, object]:
    identity = result.checkpoint["source_identity"]
    return {"workdir": str(result.workdir), "checkpoint_path": str(result.checkpoint_path), "checkpoint_sha256": result.checkpoint_sha256, "checkpoint_id": result.checkpoint["checkpoint_id"], "source_type": identity["source_type"], "source_id_kind": identity["source_id_kind"], "source_id": identity["source_id"]}


def publication_to_dict(result: PublicationResult) -> dict[str, object]:
    return {
        "title": result.title,
        "author": result.author,
        "markdown_path": str(result.markdown_path),
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
        if args.ai_advisory:
            parser.error("--ai-advisory non può essere combinato con --check.")
        return check_environment()

    if args.record_kindle_delivery is not None:
        if args.publish_from or args.review_from or args.kindle_email or args.output_dir:
            parser.error(
                "--record-kindle-delivery non può essere combinato con opzioni publish o delivery."
            )
        if args.inspect_only or args.force:
            parser.error("--record-kindle-delivery non usa --inspect-only o --force.")
        if args.ai_advisory:
            parser.error("--record-kindle-delivery non usa --ai-advisory.")
        if not args.url:
            parser.error("--record-kindle-delivery richiede l'URL della sorgente.")
        try:
            delivery = record_kindle_delivery(
                resolve_workspace(args.url, args.work_root),
                args.record_kindle_delivery,
            )
        except (DeliveryError, OSError) as error:
            print(f"ERRORE: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({"delivery": request_summary(delivery)}, ensure_ascii=False, indent=2))
        else:
            print_delivery(delivery)
        return 0

    if args.inspect_only and args.force:
        parser.error("--force non è applicabile con --inspect-only.")

    if args.inspect_only and args.publish_from:
        parser.error("--publish-from non è applicabile con --inspect-only.")

    if args.inspect_only and args.ai_advisory:
        parser.error("--ai-advisory richiede prepare completo; non usa --inspect-only.")

    if args.review_from is not None:
        if (
            args.publish_from
            or args.kindle_email
            or args.record_kindle_delivery
            or args.ai_advisory
        ):
            parser.error("--review-from non può essere combinato con publish o delivery.")
        if args.inspect_only or args.force or args.output_dir:
            parser.error("--review-from non usa --inspect-only, --force o --output-dir.")

    if args.ai_advisory and args.publish_from:
        parser.error("--ai-advisory non può essere combinato con publish o delivery.")

    if args.output_dir and not args.publish_from:
        parser.error("--output-dir richiede --publish-from.")

    if args.kindle_email and not args.publish_from:
        parser.error("--kindle-email richiede --publish-from.")

    if args.review_from is not None and not args.url:
        parser.error("--review-from richiede l'URL della sorgente.")

    if not args.url:
        parser.print_help()
        return 0

    try:
        source_type = detect_source_type(args.url)
        review: ReviewResult | None = None
        publication: PublicationResult | None = None
        delivery: DeliveryResult | None = None
        inspection = None
        preparation = None
        article = None
        ai_advisory = None

        if args.review_from is not None:
            workdir = resolve_workspace(args.url, args.work_root)
            review = review_lesson(workdir, args.review_from)
            source_type = review.checkpoint["source_identity"]["source_type"]
        elif args.publish_from is not None:
            workdir = resolve_workspace(args.url, args.work_root)
            publication = publish_lesson(workdir=workdir, source_path=args.publish_from, author=args.author, output_dir=args.output_dir)
            if args.kindle_email:
                delivery = prepare_kindle_delivery(workdir, args.kindle_email)
        elif source_type == "youtube":
            inspection = inspect_video(args.url, args.work_root)
            preparation = None if args.inspect_only else prepare_transcript(inspection.workdir, force=args.force)
            if args.ai_advisory and preparation is not None:
                ai_advisory = generate_ai_advisory(
                    preparation.workdir,
                    source_type,
                    force=args.force,
                    analyzer_factory=create_ai_analyzer,
                )
        else:
            article = ingest_article(url=args.url, work_root=args.work_root, force=args.force, inspect_only=args.inspect_only)
            if args.ai_advisory and article.analysis_markdown_path is not None:
                ai_advisory = generate_ai_advisory(
                    article.workdir,
                    source_type,
                    force=args.force,
                    analyzer_factory=create_ai_analyzer,
                )

    except (
        AIAdvisoryError,
        SourceDetectionError,
        InspectionError,
        PreparationError,
        ArticleError,
        PublicationError,
        ReviewError,
        DeliveryError,
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
        if review is not None:
            output["review"] = review_to_dict(review)

        if preparation is not None:
            output["preparation"] = preparation_to_dict(preparation)

        if article is not None:
            output["article"] = article_to_dict(article)

        if ai_advisory is not None:
            output["ai_advisory"] = ai_advisory_to_dict(ai_advisory)

        if publication is not None:
            output["publication"] = publication_to_dict(publication)

        if delivery is not None:
            output["delivery"] = request_summary(delivery)

        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        if inspection is not None:
            print_inspection(inspection)
        if review is not None:
            print_review(review)

        if preparation is not None:
            print_preparation(preparation)

        if article is not None:
            print_article(article)

        if ai_advisory is not None:
            print_ai_advisory(ai_advisory)

        if publication is not None:
            print_publication(publication)

        if delivery is not None:
            print_delivery(delivery)

    return 0


if __name__ == "__main__":
    sys.exit(main())
