"""Article inspection and preparation."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from gyte_study_tools.inspection import (
    DEFAULT_WORK_ROOT,
    atomic_write_text,
    load_state,
    slugify,
)


USER_AGENT = "Mozilla/5.0 GYTE-Study-Tools/0.5.0"
RAW_HTML_FILENAME = "article.raw.html"
EXTRACTED_FILENAME = "article.extracted.md"
ANALYSIS_FILENAME = "article.analysis.md"

SCIENTIFIC_MARKERS = (
    "nature.com/articles/",
    "doi.org/",
    "arxiv.org/",
    "pubmed",
    "sciencedirect.com/",
    "springer.com/",
    "science.org/doi/",
    "pnas.org/doi/",
)

STOP_MARKERS = {
    "tags",
    "you may like these posts",
    "post a comment",
    "previous post",
    "next post",
    "follow us",
    "popular posts",
    "categories",
}


class ArticleError(RuntimeError):
    """Raised when an article cannot be ingested safely."""


@dataclass(frozen=True)
class ArticleResult:
    workdir: Path
    metadata_path: Path
    state_path: Path
    raw_html_path: Path
    extracted_markdown_path: Path | None
    analysis_markdown_path: Path | None
    record: dict[str, Any]
    content_words: int
    reused: bool
    inspect_only: bool


class ArticleParser(HTMLParser):
    """Extract metadata and the main Blogger-style article body."""

    BLOCK_TAGS = {"h2", "h3", "p", "li", "blockquote"}
    BLOCKED_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self, source_url: str) -> None:
        super().__init__()
        self.source_url = source_url
        self.meta: dict[str, str] = {}
        self.canonical_url: str | None = None
        self.time_values: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.title_depth = 0
        self.h1_depth = 0

        self.json_ld_depth = 0
        self.json_ld_parts: list[str] = []
        self.json_ld_documents: list[str] = []

        self.content_active = False
        self.content_depth = 0
        self.blocked_depth = 0
        self.current_block_tag: str | None = None
        self.current_block_parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

        self.current_link: str | None = None
        self.current_link_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {
            key.lower(): value or ""
            for key, value in attrs
        }

        if tag == "title":
            self.title_depth += 1

        if tag == "h1":
            self.h1_depth += 1

        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
            )
            value = attributes.get("content")

            if key and value:
                self.meta[key] = html.unescape(value.strip())

        if tag == "link":
            rel = attributes.get("rel", "").lower()

            if "canonical" in rel and attributes.get("href"):
                self.canonical_url = urljoin(
                    self.source_url,
                    attributes["href"],
                )

        if tag == "time" and attributes.get("datetime"):
            self.time_values.append(attributes["datetime"].strip())

        if (
            tag == "script"
            and attributes.get("type", "").lower()
            == "application/ld+json"
        ):
            self.json_ld_depth += 1
            self.json_ld_parts = []

        classes = set(attributes.get("class", "").split())
        is_content_root = bool(
            classes.intersection({"post-body", "entry-content"})
        )

        if not self.content_active:
            if (
                tag in {"article", "main", "section", "div"}
                and is_content_root
            ):
                self.content_active = True
                self.content_depth = 1
            return

        self.content_depth += 1

        if tag in self.BLOCKED_TAGS:
            self.blocked_depth += 1

        if (
            self.blocked_depth == 0
            and tag in self.BLOCK_TAGS
            and self.current_block_tag is None
        ):
            self.current_block_tag = tag
            self.current_block_parts = []

        if (
            self.blocked_depth == 0
            and tag == "a"
            and attributes.get("href")
        ):
            self.current_link = urljoin(
                self.source_url,
                attributes["href"],
            )
            self.current_link_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

        if tag == "h1" and self.h1_depth:
            self.h1_depth -= 1

        if tag == "script" and self.json_ld_depth:
            self.json_ld_depth -= 1
            document = "".join(self.json_ld_parts).strip()

            if document:
                self.json_ld_documents.append(document)

            self.json_ld_parts = []

        if not self.content_active:
            return

        if tag == "a" and self.current_link is not None:
            text = normalize_text(" ".join(self.current_link_parts))
            self.links.append((text, self.current_link))
            self.current_link = None
            self.current_link_parts = []

        if tag == self.current_block_tag:
            text = normalize_text(" ".join(self.current_block_parts))

            if text:
                self.blocks.append((tag, text))

            self.current_block_tag = None
            self.current_block_parts = []

        if tag in self.BLOCKED_TAGS and self.blocked_depth:
            self.blocked_depth -= 1

        self.content_depth -= 1

        if self.content_depth <= 0:
            self.content_active = False
            self.content_depth = 0

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title_parts.append(data)

        if self.h1_depth:
            self.h1_parts.append(data)

        if self.json_ld_depth:
            self.json_ld_parts.append(data)

        if not self.content_active or self.blocked_depth:
            return

        if self.current_block_tag is not None:
            self.current_block_parts.append(data)

        if self.current_link is not None:
            self.current_link_parts.append(data)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def count_words(value: str) -> int:
    return len(re.findall(r"\S+", value))


def fetch_article(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get(
                "Content-Type",
                "",
            ).lower()

            if "html" not in content_type:
                raise ArticleError(
                    "La sorgente non ha restituito contenuto HTML."
                )

            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read()

    except ArticleError:
        raise
    except Exception as error:
        raise ArticleError(
            f"Download dell'articolo fallito: {error}"
        ) from error

    return payload.decode(charset, errors="replace")


def recursive_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]

        for value in payload.values():
            found = recursive_value(value, key)

            if found is not None:
                return found

    if isinstance(payload, list):
        for value in payload:
            found = recursive_value(value, key)

            if found is not None:
                return found

    return None


def parse_json_ld(
    documents: list[str],
) -> dict[str, str]:
    result: dict[str, str] = {}

    for document in documents:
        try:
            payload = json.loads(document)
        except json.JSONDecodeError:
            continue

        for source_key, destination_key in (
            ("datePublished", "published_at"),
            ("dateModified", "modified_at"),
        ):
            value = recursive_value(payload, source_key)

            if isinstance(value, str) and value.strip():
                result.setdefault(
                    destination_key,
                    value.strip(),
                )

        author = recursive_value(payload, "author")

        if isinstance(author, str):
            result.setdefault("author", author.strip())
        elif isinstance(author, dict):
            name = author.get("name")

            if isinstance(name, str) and name.strip():
                result.setdefault("author", name.strip())
        elif isinstance(author, list):
            names = []

            for entry in author:
                if isinstance(entry, str):
                    names.append(entry.strip())
                elif isinstance(entry, dict):
                    name = entry.get("name")

                    if isinstance(name, str):
                        names.append(name.strip())

            names = [name for name in names if name]

            if names:
                result.setdefault("author", ", ".join(names))

    return result


def scientific_references(
    links: list[tuple[str, str]],
) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[str] = set()

    for text, url in links:
        lowered = url.lower()

        if not any(marker in lowered for marker in SCIENTIFIC_MARKERS):
            continue

        if url in seen:
            continue

        seen.add(url)
        references.append(
            {
                "label": text or "Fonte scientifica",
                "url": url,
            }
        )

    return references


def render_extracted_markdown(
    blocks: list[tuple[str, str]],
) -> str:
    lines: list[str] = []
    seen_blocks: set[tuple[str, str]] = set()

    for tag, text in blocks:
        normalized_lower = text.casefold()

        if normalized_lower in STOP_MARKERS:
            break

        if text == "Research Paper":
            continue

        key = (tag, text)

        if key in seen_blocks:
            continue

        seen_blocks.add(key)

        if tag == "h2":
            lines.extend((f"## {text}", ""))
        elif tag == "h3":
            lines.extend((f"### {text}", ""))
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "blockquote":
            lines.extend((f"> {text}", ""))
        else:
            lines.extend((text, ""))

    return "\n".join(lines).strip() + "\n"


def build_analysis_markdown(
    record: dict[str, Any],
    extracted_markdown: str,
) -> str:
    article = record["article"]
    source = record["source"]
    references = record["scientific_references"]

    title = article["title"]
    author = article.get("author") or "non disponibile"
    published_at = article.get("published_at") or "non disponibile"
    site_name = article.get("site_name") or source["domain"]

    lines = [
        f"# {title} — articolo di lavoro",
        "",
        f"- Testata/sito: {site_name}",
        f"- Autore: {author}",
        f"- Data pubblicazione: {published_at}",
        f"- URL: {source['canonical_url']}",
        (
            "- Stato: testo giornalistico estratto automaticamente; "
            "affermazioni non ancora verificate"
        ),
        "",
        "## Contenuto estratto",
        "",
        extracted_markdown.rstrip(),
        "",
        "## Riferimenti scientifici dichiarati",
        "",
    ]

    if references:
        for reference in references:
            lines.append(
                f"- [{reference['label']}]({reference['url']})"
            )
    else:
        lines.append("- Nessun riferimento scientifico rilevato.")

    lines.extend(
        (
            "",
            "## Protocollo di analisi",
            "",
            (
                "Nella successiva Lesson Learned distinguere "
                "esplicitamente:"
            ),
            "",
            "1. le affermazioni formulate dall’articolo;",
            "2. ciò che la fonte scientifica primaria dimostra davvero;",
            "3. le inferenze proposte dall’autore dell’articolo;",
            "4. le interpretazioni o connessioni formulate durante l’analisi;",
            "5. i fatti che richiedono ulteriore verifica esterna.",
            "",
        )
    )

    return "\n".join(lines)


def choose_workdir(
    work_root: Path,
    title: str,
    source_url: str,
) -> Path:
    base = work_root / slugify(title)
    metadata_path = base / "metadata.json"

    if not base.exists() or not metadata_path.is_file():
        return base

    try:
        existing = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        existing_url = existing["source"]["requested_url"]
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ):
        existing_url = None

    if existing_url == source_url:
        return base

    suffix = hashlib.sha256(
        source_url.encode("utf-8")
    ).hexdigest()[:8]

    return work_root / f"{slugify(title)}-{suffix}"


def update_state(
    state_path: Path,
    source_id: str,
    content_words: int,
    inspect_only: bool,
    reused: bool,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    state = load_state(state_path)
    stages = state.setdefault("stages", {})

    stages["inspect"] = {
        "status": "complete",
        "completed_at": now,
        "source_type": "article",
    }

    if not inspect_only:
        stages["prepare"] = {
            "status": "complete",
            "completed_at": now,
            "source_type": "article",
            "content_words": content_words,
            "reused_existing_outputs": reused,
            "outputs": {
                "raw_html": RAW_HTML_FILENAME,
                "extracted_markdown": EXTRACTED_FILENAME,
                "analysis_markdown": ANALYSIS_FILENAME,
            },
        }

    state["schema_version"] = 1
    state["source_type"] = "article"
    state["source_id"] = source_id
    state["updated_at"] = now

    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )


def ingest_article(
    url: str,
    work_root: Path = DEFAULT_WORK_ROOT,
    force: bool = False,
    inspect_only: bool = False,
) -> ArticleResult:
    document = fetch_article(url)
    parser = ArticleParser(url)
    parser.feed(document)

    json_ld = parse_json_ld(parser.json_ld_documents)

    html_title = normalize_text(" ".join(parser.title_parts))
    h1 = normalize_text(" ".join(parser.h1_parts))

    title = (
        parser.meta.get("og:title")
        or h1
        or html_title
    )

    if not title:
        raise ArticleError(
            "Titolo dell'articolo non rilevato."
        )

    canonical_url = (
        parser.meta.get("og:url")
        or parser.canonical_url
        or url
    )

    references = scientific_references(parser.links)
    extracted_markdown = render_extracted_markdown(parser.blocks)
    content_words = count_words(extracted_markdown)

    if not inspect_only and content_words < 50:
        raise ArticleError(
            "Il contenuto principale estratto è troppo breve: "
            f"{content_words} parole."
        )

    parsed_url = urlparse(canonical_url)
    source_id = hashlib.sha256(
        canonical_url.encode("utf-8")
    ).hexdigest()[:16]

    record: dict[str, Any] = {
        "schema_version": 1,
        "source_type": "article",
        "source": {
            "requested_url": url,
            "canonical_url": canonical_url,
            "domain": parsed_url.hostname or "",
        },
        "article": {
            "title": title,
            "site_name": parser.meta.get("og:site_name"),
            "description": (
                parser.meta.get("og:description")
                or parser.meta.get("description")
            ),
            "author": (
                json_ld.get("author")
                or parser.meta.get("author")
            ),
            "published_at": (
                parser.meta.get("article:published_time")
                or json_ld.get("published_at")
                or (
                    parser.time_values[0]
                    if parser.time_values
                    else None
                )
            ),
            "modified_at": (
                parser.meta.get("article:modified_time")
                or json_ld.get("modified_at")
            ),
        },
        "extraction": {
            "strategy": "post-body-or-entry-content",
            "content_words": content_words,
        },
        "scientific_references": references,
    }

    work_root = work_root.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    workdir = choose_workdir(work_root, title, url)
    workdir.mkdir(parents=True, exist_ok=True)

    metadata_path = workdir / "metadata.json"
    state_path = workdir / "pipeline-state.json"
    raw_html_path = workdir / RAW_HTML_FILENAME
    extracted_path = workdir / EXTRACTED_FILENAME
    analysis_path = workdir / ANALYSIS_FILENAME
    source_url_path = workdir / "source-url.txt"

    required_paths = [
        metadata_path,
        state_path,
        raw_html_path,
        source_url_path,
    ]

    if not inspect_only:
        required_paths.extend(
            [extracted_path, analysis_path]
        )

    if (
        not force
        and all(
            path.is_file() and path.stat().st_size > 0
            for path in required_paths
        )
    ):
        existing_record = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        existing_words = (
            existing_record.get("extraction", {})
            .get("content_words", content_words)
        )

        update_state(
            state_path=state_path,
            source_id=source_id,
            content_words=existing_words,
            inspect_only=inspect_only,
            reused=True,
        )

        return ArticleResult(
            workdir=workdir,
            metadata_path=metadata_path,
            state_path=state_path,
            raw_html_path=raw_html_path,
            extracted_markdown_path=(
                None if inspect_only else extracted_path
            ),
            analysis_markdown_path=(
                None if inspect_only else analysis_path
            ),
            record=existing_record,
            content_words=existing_words,
            reused=True,
            inspect_only=inspect_only,
        )

    atomic_write_text(source_url_path, url + "\n")
    atomic_write_text(raw_html_path, document)
    atomic_write_text(
        metadata_path,
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
    )

    if not inspect_only:
        analysis_markdown = build_analysis_markdown(
            record,
            extracted_markdown,
        )
        atomic_write_text(extracted_path, extracted_markdown)
        atomic_write_text(analysis_path, analysis_markdown)

    update_state(
        state_path=state_path,
        source_id=source_id,
        content_words=content_words,
        inspect_only=inspect_only,
        reused=False,
    )

    return ArticleResult(
        workdir=workdir,
        metadata_path=metadata_path,
        state_path=state_path,
        raw_html_path=raw_html_path,
        extracted_markdown_path=(
            None if inspect_only else extracted_path
        ),
        analysis_markdown_path=(
            None if inspect_only else analysis_path
        ),
        record=record,
        content_words=content_words,
        reused=False,
        inspect_only=inspect_only,
    )
