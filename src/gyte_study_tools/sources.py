"""Detection of supported source types."""

from __future__ import annotations

from urllib.parse import urlparse


class SourceDetectionError(ValueError):
    """Raised when a URL cannot be classified safely."""


def detect_source_type(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if parsed.scheme not in {"http", "https"} or not host:
        raise SourceDetectionError(
            "La sorgente deve essere un URL HTTP o HTTPS valido."
        )

    youtube_hosts = {
        "youtu.be",
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }

    if host in youtube_hosts or host.endswith(".youtube.com"):
        return "youtube"

    return "article"
