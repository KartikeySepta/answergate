"""
Tests for the MCP server — offline, no network, no models.

  python3 -m pytest rag/tests/test_mcp_server.py -v
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server import PROTOCOL_VERSION, TOOLS, handle, serve


def req(method, rid=1, **params):
    r = {"jsonrpc": "2.0", "method": method}
    if rid is not None:
        r["id"] = rid
    if params:
        r["params"] = params
    return r


# ─── HANDSHAKE ────────────────────────────────────────────────────────────────

def test_initialize_returns_protocol_and_server_info():
    r = handle(req("initialize"))
    assert r["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert r["result"]["serverInfo"]["name"] == "answergate"
    assert "tools" in r["result"]["capabilities"]


def test_notifications_get_no_reply():
    """A JSON-RPC notification has no id; replying to one is a protocol violation."""
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# ─── TOOL DISCOVERY ───────────────────────────────────────────────────────────

def test_lists_both_tools():
    names = {t["name"] for t in handle(req("tools/list"))["result"]["tools"]}
    assert names == {"search_clips", "list_workspaces"}


def test_every_tool_has_a_schema_with_required_fields_declared():
    for t in TOOLS:
        assert t["inputSchema"]["type"] == "object"
        for field in t["inputSchema"].get("required", []):
            assert field in t["inputSchema"]["properties"], (t["name"], field)


def test_search_clips_description_states_it_can_return_nothing():
    """The refusal behaviour is the point; an agent must know to expect it."""
    d = next(t for t in TOOLS if t["name"] == "search_clips")["description"].lower()
    assert "nothing" in d or "empty" in d


# ─── ERRORS ───────────────────────────────────────────────────────────────────

def test_unknown_method_is_a_protocol_error():
    assert handle(req("does/notexist"))["error"]["code"] == -32601


def test_unknown_tool_is_a_protocol_error():
    r = handle(req("tools/call", name="nope"))
    assert r["error"]["code"] == -32601


def test_missing_arguments_are_reported_not_guessed():
    r = handle(req("tools/call", name="search_clips", arguments={"workspace": "w"}))
    assert r["error"]["code"] == -32602
    assert "question" in r["error"]["message"]


def test_tool_failure_returns_readable_output_not_a_dead_call():
    """An exception inside a tool becomes isError content the agent can actually read."""
    r = handle(req("tools/call", name="search_clips",
                   arguments={"workspace": "../etc/passwd", "question": "x"}))
    assert r["result"]["isError"] is True
    assert "answergate failed" in r["result"]["content"][0]["text"]


# ─── TRANSPORT ────────────────────────────────────────────────────────────────

def test_serve_reads_lines_and_writes_one_response_per_request():
    stdin = io.StringIO(json.dumps(req("initialize")) + "\n"
                        + json.dumps(req("tools/list", rid=2)) + "\n")
    out = io.StringIO()
    serve(stdin, out)
    lines = [l for l in out.getvalue().split("\n") if l]
    assert len(lines) == 2
    assert json.loads(lines[1])["id"] == 2


def test_malformed_frame_does_not_kill_the_session():
    stdin = io.StringIO("this is not json\n" + json.dumps(req("initialize")) + "\n")
    out = io.StringIO()
    serve(stdin, out)
    assert len([l for l in out.getvalue().split("\n") if l]) == 1


def test_blank_lines_are_skipped():
    stdin = io.StringIO("\n\n" + json.dumps(req("initialize")) + "\n")
    out = io.StringIO()
    serve(stdin, out)
    assert len([l for l in out.getvalue().split("\n") if l]) == 1
