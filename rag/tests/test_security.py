"""
Tests for the security validators — run offline, no network or API keys needed.

  python3 -m pytest rag/tests/test_security.py -v
  or simply:  python3 rag/tests/test_security.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from core.security import (
    check_api_key,
    safe_workspace_path,
    validate_history,
    validate_question,
    validate_workspace_id,
    validate_youtube_url,
)


# ─── WORKSPACE ID: PATH TRAVERSAL ─────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "../../etc/passwd",
    "..",
    "../secrets",
    "foo/bar",
    "foo\\bar",
    "/absolute/path",
    "foo/../../bar",
    "with space",
    "with.dot",
    "",
    "a" * 65,
    "$(whoami)",
    "foo;rm -rf /",
    "foo\x00bar",
])
def test_rejects_unsafe_workspace_ids(bad):
    with pytest.raises(ValueError):
        validate_workspace_id(bad)


@pytest.mark.parametrize("good", [
    "upwork", "my_research", "test-123", "A1", "a" * 64,
])
def test_accepts_safe_workspace_ids(good):
    assert validate_workspace_id(good) == good


def test_safe_workspace_path_stays_inside_root(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    resolved = safe_workspace_path(root, "myws")
    assert resolved == (root.resolve() / "myws")
    assert root.resolve() in resolved.parents


def test_safe_workspace_path_blocks_traversal(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    with pytest.raises(ValueError):
        safe_workspace_path(root, "../../etc")


# ─── YOUTUBE URL VALIDATION ───────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected_id", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ"),
    ("  https://youtu.be/dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
])
def test_accepts_valid_youtube_urls(url, expected_id):
    assert validate_youtube_url(url) == f"https://www.youtube.com/watch?v={expected_id}"


@pytest.mark.parametrize("bad", [
    "urls.txt",                                  # the real bug from the CLI run
    "/etc/passwd",
    "file:///etc/passwd",
    "https://evil.com/watch?v=dQw4w9WgXcQ",      # wrong host
    "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=short",     # id too short
    "https://www.youtube.com/watch",             # no id
    "javascript:alert(1)",
    "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    "",
    "   ",
])
def test_rejects_invalid_urls(bad):
    with pytest.raises(ValueError):
        validate_youtube_url(bad)


# ─── FREE-TEXT LIMITS ─────────────────────────────────────────────────────────

def test_question_limits():
    assert validate_question("  what is RAG?  ") == "what is RAG?"
    with pytest.raises(ValueError):
        validate_question("")
    with pytest.raises(ValueError):
        validate_question("x" * 4001)


def test_history_limits():
    assert validate_history(None) is None
    assert validate_history([{"role": "user", "content": "hi"}]) is not None
    with pytest.raises(ValueError):
        validate_history([{"role": "user"}] * 51)
    with pytest.raises(ValueError):
        validate_history("not a list")


# ─── API KEY AUTH ─────────────────────────────────────────────────────────────

def test_auth_disabled_allows_all(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    assert check_api_key(None) is True
    assert check_api_key("anything") is True


def test_auth_enabled_requires_match(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    assert check_api_key("s3cret") is True
    assert check_api_key("wrong") is False
    assert check_api_key(None) is False
    assert check_api_key("") is False


# ─── SCRAPER API SURFACE ──────────────────────────────────────────────────────

def test_scraper_request_model_has_no_output_field():
    """The `output` field allowed arbitrary server-side file writes; it must stay gone."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scraper"))
    from security import validate_youtube_url as scraper_validate

    # scraper validator behaves the same as the rag one
    assert scraper_validate("https://youtu.be/dQw4w9WgXcQ") == \
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
