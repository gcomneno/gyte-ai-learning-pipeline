"""Publish a reviewed source lesson as semantic HTML, PDF and EPUB."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from gyte_study_tools.inspection import atomic_write_text, load_state


DEFAULT_AUTHOR = "Giancarlo e ChatGPT"
BACKTICK = chr(96)
MARKDOWN_FENCE = BACKTICK * 3


class PublicationError(RuntimeError):
    """Raised when publication cannot be completed safely."""


@dataclass(frozen=True)
class ConversionMetrics:
    source_words: int
    pdf_words: int
    epub_words: int


@dataclass(frozen=True)
class PublicationResult:
    workdir: Path
    source_path: Path
    markdown_path: Path
    html_path: Path
    pdf_path: Path
    epub_path: Path
    manifest_path: Path
    title: str
    author: str
    metrics: ConversionMetrics
    backups: dict[str, str]


class VisibleTextParser(HTMLParser):
    """Collect visible textual content from generated HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"style", "script"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"} and self.hidden_depth > 0:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0 and data.strip():
            self.parts.append(data)


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def extract_heading(markdown: str) -> str:
    headings = [
        match.group(1).strip()
        for line in markdown.splitlines()
        if (match := re.match(r"^#\s+(.+?)\s*$", line))
    ]

    if len(headings) != 1:
        raise PublicationError(
            "La lezione sorgente deve contenere esattamente un titolo Markdown H1."
        )

    return headings[0]


def normalize_publication_title(heading: str) -> str:
    """Keep the reviewed H1 unchanged when deriving publication metadata."""
    return heading.strip()


def filename_stem(title: str) -> str:
    value = title.replace("—", "-")
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .-")
    return value or "lesson"


def render_inline(text: str) -> str:
    code_tokens: list[str] = []
    code_pattern = re.compile(
        re.escape(BACKTICK) + r"([^" + re.escape(BACKTICK) + r"]+)"
        + re.escape(BACKTICK)
    )

    def protect_code(match: re.Match[str]) -> str:
        token = f"@@GYTE_CODE_{len(code_tokens)}@@"
        code_tokens.append(
            "<code>" + html.escape(match.group(1), quote=False) + "</code>"
        )
        return token

    protected = code_pattern.sub(protect_code, text)
    rendered = html.escape(protected, quote=False)

    rendered = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2">\1</a>',
        rendered,
    )
    rendered = re.sub(
        r"\*\*(.+?)\*\*",
        r"<strong>\1</strong>",
        rendered,
    )
    rendered = re.sub(
        r"(?<!\*)\*([^*]+?)\*(?!\*)",
        r"<em>\1</em>",
        rendered,
    )

    for index, code_html in enumerate(code_tokens):
        rendered = rendered.replace(
            f"@@GYTE_CODE_{index}@@",
            code_html,
        )

    return rendered


def starts_block(line: str) -> bool:
    stripped = line.lstrip()

    return bool(
        not stripped
        or stripped.startswith(MARKDOWN_FENCE)
        or re.match(r"^#{1,6}\s+", stripped)
        or re.match(r"^[-*_]\s*[-*_]\s*[-*_]", stripped)
        or stripped.startswith("> ")
        or re.match(r"^[-*+]\s+", stripped)
        or re.match(r"^\d+[.)]\s+", stripped)
    )


def render_markdown_body(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith(MARKDOWN_FENCE):
            language = stripped[len(MARKDOWN_FENCE):].strip()
            index += 1
            code_lines: list[str] = []

            while (
                index < len(lines)
                and not lines[index].strip().startswith(MARKDOWN_FENCE)
            ):
                code_lines.append(lines[index])
                index += 1

            if index < len(lines):
                index += 1

            language_class = (
                f' class="language-{html.escape(language)}"'
                if language
                else ""
            )
            code = html.escape("\n".join(code_lines), quote=False)
            output.append(
                f"<pre><code{language_class}>{code}</code></pre>"
            )
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)

        if heading:
            level = len(heading.group(1))
            output.append(
                f"<h{level}>{render_inline(heading.group(2))}</h{level}>"
            )
            index += 1
            continue

        if re.match(r"^[-*_]\s*[-*_]\s*[-*_]", stripped):
            output.append("<hr>")
            index += 1
            continue

        if stripped.startswith("> "):
            quote_lines: list[str] = []

            while index < len(lines):
                current = lines[index].strip()

                if not current.startswith(">"):
                    break

                quote_lines.append(current[1:].lstrip())
                index += 1

            quote_text = " ".join(quote_lines)
            output.append(
                "<blockquote><p>"
                + render_inline(quote_text)
                + "</p></blockquote>"
            )
            continue

        if re.match(r"^[-*+]\s+", stripped):
            items: list[str] = []

            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^[-*+]\s+(.+)$", current)

                if not match:
                    break

                items.append(
                    "<li>" + render_inline(match.group(1)) + "</li>"
                )
                index += 1

            output.append("<ul>" + "".join(items) + "</ul>")
            continue

        if re.match(r"^\d+[.)]\s+", stripped):
            items = []

            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^\d+[.)]\s+(.+)$", current)

                if not match:
                    break

                items.append(
                    "<li>" + render_inline(match.group(1)) + "</li>"
                )
                index += 1

            output.append("<ol>" + "".join(items) + "</ol>")
            continue

        paragraph_lines = [stripped]
        index += 1

        while index < len(lines) and not starts_block(lines[index]):
            paragraph_lines.append(lines[index].strip())
            index += 1

        paragraph = " ".join(part for part in paragraph_lines if part)
        output.append("<p>" + render_inline(paragraph) + "</p>")

    return "\n".join(output)


def render_document(
    markdown: str,
    title: str,
    author: str,
) -> str:
    body = render_markdown_body(markdown)

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="author" content="{html.escape(author, quote=True)}">
  <title>{html.escape(title)}</title>
  <style>
    @page {{
      margin: 18mm 17mm 20mm;
    }}

    body {{
      font-family: serif;
      font-size: 1em;
      line-height: 1.55;
      max-width: 42em;
      margin: 0 auto;
      padding: 1.5em;
    }}

    h1, h2, h3 {{
      line-height: 1.2;
      page-break-after: avoid;
    }}

    h1 {{
      margin-bottom: 1.3em;
    }}

    h2 {{
      margin-top: 1.7em;
    }}

    p, li {{
      orphans: 3;
      widows: 3;
    }}

    blockquote {{
      border-left: 0.25em solid #888;
      margin-left: 0;
      padding-left: 1em;
      font-style: italic;
    }}

    code {{
      font-family: monospace;
    }}

    pre {{
      white-space: pre-wrap;
      padding: 0.8em;
      border: 1px solid #aaa;
    }}

    a {{
      color: inherit;
      text-decoration: underline;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def visible_html_text(document: str) -> str:
    parser = VisibleTextParser()
    parser.feed(document)
    return "\n".join(parser.parts)


def run_command(command: list[str], description: str) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PublicationError(
            f"{description}."
            + (f" Dettaglio: {detail}" if detail else "")
        )


def validate_epub(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            damaged = archive.testzip()

            if damaged is not None:
                raise PublicationError(
                    f"Elemento EPUB danneggiato: {damaged}"
                )

            if "mimetype" not in archive.namelist():
                raise PublicationError(
                    "Il file EPUB non contiene mimetype."
                )

            mimetype = archive.read("mimetype").decode(
                "ascii",
                errors="replace",
            ).strip()

            if mimetype != "application/epub+zip":
                raise PublicationError(
                    f"Mimetype EPUB inatteso: {mimetype}"
                )
    except zipfile.BadZipFile as error:
        raise PublicationError(
            "Il file prodotto non è un archivio EPUB valido."
        ) from error


def build_converted_outputs(
    html_path: Path,
    pdf_path: Path,
    epub_path: Path,
    title: str,
    author: str,
    source_words: int,
    temporary_directory: Path,
) -> ConversionMetrics:
    ebook_convert = shutil.which("ebook-convert")
    pdftotext = shutil.which("pdftotext")

    if ebook_convert is None:
        raise PublicationError(
            "ebook-convert non è disponibile nel PATH."
        )

    if pdftotext is None:
        raise PublicationError(
            "pdftotext non è disponibile nel PATH."
        )

    run_command(
        [
            ebook_convert,
            str(html_path),
            str(epub_path),
            "--title",
            title,
            "--authors",
            author,
            "--language",
            "it",
        ],
        "Conversione HTML → EPUB fallita",
    )

    run_command(
        [
            ebook_convert,
            str(html_path),
            str(pdf_path),
            "--title",
            title,
            "--authors",
            author,
            "--language",
            "it",
        ],
        "Conversione HTML → PDF fallita",
    )

    if not epub_path.is_file() or epub_path.stat().st_size == 0:
        raise PublicationError("EPUB prodotto assente o vuoto.")

    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PublicationError("PDF prodotto assente o vuoto.")

    validate_epub(epub_path)

    epub_text = temporary_directory / "epub-roundtrip.txt"
    pdf_text = temporary_directory / "pdf-roundtrip.txt"

    run_command(
        [
            ebook_convert,
            str(epub_path),
            str(epub_text),
        ],
        "Estrazione testuale EPUB fallita",
    )
    run_command(
        [
            pdftotext,
            "-nopgbrk",
            str(pdf_path),
            str(pdf_text),
        ],
        "Estrazione testuale PDF fallita",
    )

    epub_words = count_words(
        epub_text.read_text(encoding="utf-8", errors="replace")
    )
    pdf_words = count_words(
        pdf_text.read_text(encoding="utf-8", errors="replace")
    )

    minimum_words = max(1, int(source_words * 0.85))

    if epub_words < minimum_words:
        raise PublicationError(
            "L'EPUB contiene troppo poco testo: "
            f"{epub_words} parole su almeno {minimum_words} attese."
        )

    if pdf_words < minimum_words:
        raise PublicationError(
            "Il PDF contiene troppo poco testo: "
            f"{pdf_words} parole su almeno {minimum_words} attese."
        )

    return ConversionMetrics(
        source_words=source_words,
        pdf_words=pdf_words,
        epub_words=epub_words,
    )


def next_backup_path(path: Path, timestamp: str) -> Path:
    candidate = path.with_name(
        f"{path.stem}.backup-{timestamp}{path.suffix}"
    )
    counter = 2

    while candidate.exists():
        candidate = path.with_name(
            f"{path.stem}.backup-{timestamp}-{counter}{path.suffix}"
        )
        counter += 1

    return candidate


def backup_existing(path: Path, timestamp: str) -> Path | None:
    if not path.exists():
        return None

    backup = next_backup_path(path, timestamp)
    path.replace(backup)
    return backup


def update_publish_state(
    state_path: Path,
    title: str,
    author: str,
    markdown_path: Path,
    html_path: Path,
    pdf_path: Path,
    epub_path: Path,
    manifest_path: Path,
    metrics: ConversionMetrics,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    stages = state.setdefault("stages", {})

    stages["publish"] = {
        "status": "complete",
        "completed_at": now,
        "title": title,
        "author": author,
        "outputs": {
            "markdown": str(markdown_path),
            "html": str(html_path),
            "pdf": str(pdf_path),
            "epub": str(epub_path),
            "manifest": str(manifest_path),
        },
        "word_counts": {
            "source": metrics.source_words,
            "pdf": metrics.pdf_words,
            "epub": metrics.epub_words,
        },
    }
    state["updated_at"] = now

    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def publish_lesson(
    workdir: Path,
    source_path: Path,
    author: str = DEFAULT_AUTHOR,
    output_dir: Path | None = None,
) -> PublicationResult:
    workdir = workdir.expanduser().resolve()
    source_path = source_path.expanduser().resolve()

    if not source_path.is_file():
        raise PublicationError(
            f"Lezione sorgente Markdown non trovata: {source_path}"
        )

    markdown = source_path.read_text(encoding="utf-8")

    if not markdown.strip():
        raise PublicationError("La lezione sorgente Markdown è vuota.")

    heading = extract_heading(markdown)
    title = normalize_publication_title(heading)
    stem = filename_stem(title)

    publication_dir = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else workdir / "publication"
    )
    publication_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = publication_dir / f"{stem}.md"
    html_path = publication_dir / f"{stem}.html"
    pdf_path = publication_dir / f"{stem}.pdf"
    epub_path = publication_dir / f"{stem}.epub"
    manifest_path = publication_dir / "publication-manifest.json"
    state_path = workdir / "pipeline-state.json"

    html_document = render_document(markdown, title, author)
    source_words = count_words(visible_html_text(html_document))

    if source_words == 0:
        raise PublicationError(
            "La sorgente HTML non contiene testo visibile."
        )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups: dict[str, str] = {}

    with tempfile.TemporaryDirectory(
        prefix=".gyte-publish-",
        dir=publication_dir,
    ) as temporary:
        temporary_directory = Path(temporary)
        temporary_html = temporary_directory / "lesson.html"
        temporary_pdf = temporary_directory / "lesson.pdf"
        temporary_epub = temporary_directory / "lesson.epub"

        temporary_html.write_text(
            html_document,
            encoding="utf-8",
        )

        metrics = build_converted_outputs(
            html_path=temporary_html,
            pdf_path=temporary_pdf,
            epub_path=temporary_epub,
            title=title,
            author=author,
            source_words=source_words,
            temporary_directory=temporary_directory,
        )

        for destination in (
            markdown_path,
            html_path,
            pdf_path,
            epub_path,
            manifest_path,
        ):
            backup = backup_existing(destination, timestamp)

            if backup is not None:
                backups[str(destination)] = str(backup)

        atomic_write_text(markdown_path, markdown)
        atomic_write_text(html_path, html_document)
        temporary_pdf.replace(pdf_path)
        temporary_epub.replace(epub_path)

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "published_at": now,
        "title": title,
        "author": author,
        "files": {
            "markdown": {
                "path": markdown_path.name,
                "sha256": sha256_file(markdown_path),
            },
            "html": {
                "path": html_path.name,
                "sha256": sha256_file(html_path),
            },
            "pdf": {
                "path": pdf_path.name,
                "sha256": sha256_file(pdf_path),
                "words": metrics.pdf_words,
            },
            "epub": {
                "path": epub_path.name,
                "sha256": sha256_file(epub_path),
                "words": metrics.epub_words,
            },
        },
        "source_words": metrics.source_words,
        "backups": backups,
    }

    atomic_write_text(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )

    update_publish_state(
        state_path=state_path,
        title=title,
        author=author,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        epub_path=epub_path,
        manifest_path=manifest_path,
        metrics=metrics,
    )

    return PublicationResult(
        workdir=workdir,
        source_path=source_path,
        markdown_path=markdown_path,
        html_path=html_path,
        pdf_path=pdf_path,
        epub_path=epub_path,
        manifest_path=manifest_path,
        title=title,
        author=author,
        metrics=metrics,
        backups=backups,
    )
