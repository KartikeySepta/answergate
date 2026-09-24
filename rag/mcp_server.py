"""
MCP SERVER — let a coding agent query your video corpus.

Exposes the answer gate over the Model Context Protocol, so Claude Code, Cursor, VS Code
or any MCP client can ask a question across your ingested videos and get back timestamped
clips that ANSWER it — including getting back nothing, when nothing does.

Deliberately dependency-free. MCP is JSON-RPC 2.0 over stdin/stdout, which is ~100 lines of
stdlib; pulling in an SDK would add install weight to a project whose biggest adoption
problem is already install weight.

Register it with an MCP client:

  {
    "mcpServers": {
      "answergate": {
        "command": "python3",
        "args": ["/absolute/path/to/rag/mcp_server.py"],
        "env": {"GEMINI_API_KEY": "..."}
      }
    }
  }

Offline self-test (no network, no models):
  python3 mcp_server.py --test-protocol
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "answergate", "version": "0.1.0"}

TOOLS = [
    {
        "name": "search_clips",
        "description": (
            "Find the moments in an ingested video corpus that ANSWER a question. Returns "
            "timestamped clips with verbatim quotes and YouTube links, plus which videos "
            "contained nothing relevant. Returns an empty list when no source answers the "
            "question — it does not fall back to the nearest-sounding passage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string",
                              "description": "Workspace id, e.g. 'my_research'"},
                "question": {"type": "string",
                             "description": "A specific question to answer from the videos"},
            },
            "required": ["workspace", "question"],
        },
    },
    {
        "name": "list_workspaces",
        "description": "List the video corpora available to search, with video counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ─── tool implementations ─────────────────────────────────────────────────────

def _workspaces_dir() -> Path:
    from core.config import WORKSPACES_DIR
    return Path(WORKSPACES_DIR)


def tool_list_workspaces() -> str:
    base = _workspaces_dir()
    if not base.exists():
        return "No workspaces yet. Create one with: python3 cli.py add <url> <workspace>"
    rows = []
    for d in sorted(base.iterdir()):
        videos = d / "videos.json"
        if not videos.is_file():
            continue
        try:
            n = len(json.loads(videos.read_text()))
        except Exception:
            n = 0
        rows.append(f"- {d.name} ({n} video{'s' if n != 1 else ''})")
    return "\n".join(rows) if rows else "No workspaces yet."


def tool_search_clips(workspace: str, question: str) -> str:
    from core.security import validate_workspace_id
    from retrieval.clips import find_clips, render_clips

    workspace = validate_workspace_id(workspace)   # path-traversal guard, same as the API
    return render_clips(find_clips(question, workspace_id=workspace))


# ─── JSON-RPC plumbing ────────────────────────────────────────────────────────

def handle(request: dict) -> dict | None:
    """Return a JSON-RPC response, or None for notifications (which take no reply)."""
    method = request.get("method", "")
    req_id = request.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {"tools": {}},
                   "serverInfo": SERVER_INFO})

    # Notifications have no id and must not be answered.
    if req_id is None:
        return None

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "list_workspaces":
                text = tool_list_workspaces()
            elif name == "search_clips":
                missing = [k for k in ("workspace", "question") if not args.get(k)]
                if missing:
                    return err(-32602, f"missing required argument(s): {', '.join(missing)}")
                text = tool_search_clips(args["workspace"], args["question"])
            else:
                return err(-32601, f"unknown tool: {name}")
        except Exception as e:
            # Surface the failure as tool output rather than a protocol error, so the agent
            # can read it and react instead of the whole call vanishing.
            return ok({"content": [{"type": "text", "text": f"answergate failed: {e}"}],
                       "isError": True})
        return ok({"content": [{"type": "text", "text": text}]})

    return err(-32601, f"unknown method: {method}")


def serve(stdin=None, stdout=None) -> None:
    """Read line-delimited JSON-RPC from stdin, write responses to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue          # a malformed frame must not kill the session
        response = handle(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-protocol":
        init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert init["result"]["serverInfo"]["name"] == "answergate", init
        tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert {t["name"] for t in tools["result"]["tools"]} == {"search_clips",
                                                                 "list_workspaces"}, tools
        assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        bad = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "nope"}})
        assert bad["error"]["code"] == -32601, bad
        miss = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                       "params": {"name": "search_clips", "arguments": {"workspace": "w"}}})
        assert miss["error"]["code"] == -32602, miss
        print("MCP protocol OK (initialize, tools/list, notifications, unknown tool, bad args)")
        sys.exit(0)

    serve()
