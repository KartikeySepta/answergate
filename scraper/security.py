"""
Security helpers for the scraper API — URL validation and API key auth.

Kept standalone (no rag/ import) so the scraper stays deployable on its own.
Mirrors rag/core/security.py; keep the two in sync if you change the rules.
"""

import hmac
import os
import re
from urllib.parse import urlparse, parse_qs

_ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be", "www.youtu.be",
}

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def validate_youtube_url(url: str) -> str:
    """
    Return a normalised YouTube watch URL, or raise ValueError.

    Rejects non-HTTP schemes, non-YouTube hosts, and local file paths — the
    last of which is how 'urls.txt' previously reached yt-dlp.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must start with http:// or https:// (got '{url}')")

    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"Only YouTube URLs are allowed (got host '{host}')")

    video_id = _extract_video_id(parsed)
    if not video_id:
        raise ValueError(f"Could not find a valid YouTube video id in '{url}'")

    return f"https://www.youtube.com/watch?v={video_id}"


def _extract_video_id(parsed) -> str | None:
    """Pull the 11-char video id out of any supported YouTube URL shape."""
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if host in ("youtu.be", "www.youtu.be"):
        candidate = path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    if path == "/watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
        if path.startswith(prefix):
            candidate = path[len(prefix):].split("/")[0]
            return candidate if _VIDEO_ID_RE.match(candidate) else None

    return None


# ─── API KEY AUTH ──────────────────────────────────────────────────────────────

def get_expected_api_key() -> str | None:
    """Shared secret required in the X-API-Key header; None means auth disabled."""
    key = os.getenv("API_KEY", "").strip()
    return key or None


def auth_enabled() -> bool:
    return get_expected_api_key() is not None


def check_api_key(provided: str | None) -> bool:
    """Constant-time comparison against the configured key."""
    expected = get_expected_api_key()
    if expected is None:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)
