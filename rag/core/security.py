"""
Security helpers — input validation and authentication for the API layer.

Three concerns handled here:
  1. workspace_id validation  → prevents path traversal (../../etc/passwd)
  2. YouTube URL validation   → prevents feeding arbitrary URLs/files to yt-dlp
  3. API key authentication   → prevents anonymous callers burning your LLM quota

All validators raise ValueError on bad input so callers can map them to HTTP 400.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ─── WORKSPACE ID ──────────────────────────────────────────────────────────────

# Whitelist: letters, digits, underscore, hyphen. No dots, no slashes, no spaces.
# This makes path traversal structurally impossible rather than relying on a blocklist.
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_workspace_id(workspace_id: str) -> str:
    """
    Return the workspace_id if it is safe to use as a single path segment.

    Raises ValueError otherwise. Rejects '..', '/', '\\', absolute paths,
    empty strings, and anything longer than 64 chars.
    """
    if not isinstance(workspace_id, str) or not workspace_id:
        raise ValueError("workspace_id must be a non-empty string")

    if not _WORKSPACE_ID_RE.match(workspace_id):
        raise ValueError(
            f"Invalid workspace_id '{workspace_id}'. "
            "Use only letters, numbers, underscore, and hyphen (max 64 chars)."
        )

    return workspace_id


def safe_workspace_path(workspaces_dir: str | Path, workspace_id: str) -> Path:
    """
    Build a workspace path that is guaranteed to stay inside workspaces_dir.

    Validates the id first, then verifies the resolved path is still a
    descendant of the root — defence in depth against symlink tricks.
    """
    validate_workspace_id(workspace_id)

    root = Path(workspaces_dir).resolve()
    candidate = (root / workspace_id).resolve()

    if candidate != root and root not in candidate.parents:
        raise ValueError(f"workspace_id '{workspace_id}' resolves outside the workspaces directory")

    return candidate


# ─── YOUTUBE URL ───────────────────────────────────────────────────────────────

_ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be", "www.youtu.be",
}

# YouTube video ids are exactly 11 chars of [A-Za-z0-9_-]
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def validate_youtube_url(url: str) -> str:
    """
    Return a normalised YouTube watch URL, or raise ValueError.

    Accepts the common shapes (watch?v=, youtu.be/, /shorts/, /embed/) and
    rejects everything else — including local file paths, which is how
    'urls.txt' previously reached yt-dlp and produced a confusing crash.
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

    # youtu.be/<id>
    if host in ("youtu.be", "www.youtu.be"):
        candidate = path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    # youtube.com/watch?v=<id>
    if path == "/watch":
        candidate = (parse_qs(parsed.query).get("v") or [""])[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    # youtube.com/shorts/<id>, /embed/<id>, /live/<id>, /v/<id>
    for prefix in ("/shorts/", "/embed/", "/live/", "/v/"):
        if path.startswith(prefix):
            candidate = path[len(prefix):].split("/")[0]
            return candidate if _VIDEO_ID_RE.match(candidate) else None

    return None


# ─── FREE-TEXT LIMITS ──────────────────────────────────────────────────────────

MAX_QUESTION_CHARS = 4000
MAX_HISTORY_MESSAGES = 50


def validate_question(question: str) -> str:
    """Reject empty or oversized questions before they reach the LLM."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"question too long ({len(question)} chars, max {MAX_QUESTION_CHARS})")
    return question.strip()


def validate_history(history: list[dict] | None) -> list[dict] | None:
    """Cap conversation history so a caller cannot blow up the prompt budget."""
    if history is None:
        return None
    if not isinstance(history, list):
        raise ValueError("history must be a list of messages")
    if len(history) > MAX_HISTORY_MESSAGES:
        raise ValueError(f"history too long ({len(history)} messages, max {MAX_HISTORY_MESSAGES})")
    return history


# ─── API KEY AUTH ──────────────────────────────────────────────────────────────

def get_expected_api_key() -> str | None:
    """
    The shared secret callers must present in the X-API-Key header.

    Returns None when API_KEY is unset, which leaves the API open — fine for
    local single-user work, unsafe once the port is reachable from elsewhere.
    """
    key = os.getenv("API_KEY", "").strip()
    return key or None


def auth_enabled() -> bool:
    """True when an API_KEY is configured."""
    return get_expected_api_key() is not None


def check_api_key(provided: str | None) -> bool:
    """Constant-time comparison of the provided key against the configured one."""
    import hmac

    expected = get_expected_api_key()
    if expected is None:
        return True  # auth disabled
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)
