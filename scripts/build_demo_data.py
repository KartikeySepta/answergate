"""
Generate the static demo's data by running the REAL answer gate over a real workspace.

The demo has to be trustworthy or it is worse than no demo: every span it shows is
verbatim from a real transcript, every timestamp is the real chunk boundary, and every
verdict comes from an actual LLM call through find_clips — not a mock-up.

One honest substitution. Full retrieval needs sentence-transformers and rank_bm25; where
those are unavailable this falls back to a lexical retriever (term overlap) to pick the
candidate chunks the gate then judges. That changes WHICH chunks are considered, never what
the viewer is shown, and the generated file records which retriever ran so nobody has to
guess. With the full stack installed it uses the real hybrid+rerank path automatically.

  python3 scripts/build_demo_data.py [workspace_id]

Writes docs/demo/data/clips.json.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag"))

OUT = ROOT / "docs" / "demo" / "data" / "clips.json"

# Chosen to show the range of behaviours, including the one nobody else demonstrates:
# a question the corpus genuinely cannot answer, where the honest output is nothing.
QUESTIONS = [
    "Does MCP replace my existing APIs?",
    "What are the three parts of MCP?",
    "Is it safe to install a random MCP server?",
    "How do I add an MCP server to Cursor or Claude Desktop?",
    "How much does Claude Pro cost per month?",
]

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def make_lexical_retriever(chunks: list[dict], top_k: int = 8):
    """Stand-in for hybrid+rerank when the ML stack is absent.

    Scores by how much of the QUESTION a chunk covers (containment, not Jaccard) so long
    chunks aren't punished for being long. Sets rerank_score because find_clips sorts on it.
    """
    stop = _tokens("a an the is are do does did how what when where why which to of for "
                   "in on with my your i you it this that and or if can should my me")

    def retrieve(question: str, workspace_id: str) -> list[dict]:
        q = _tokens(question) - stop
        scored = []
        for c in chunks:
            overlap = len(q & _tokens(c["text"]))
            if overlap:
                scored.append((overlap / max(len(q), 1), c))
        scored.sort(key=lambda x: -x[0])
        return [{**c, "rerank_score": round(s, 4)} for s, c in scored[:top_k]]

    return retrieve


def main() -> int:
    from retrieval.clips import find_clips

    workspace_id = sys.argv[1] if len(sys.argv) > 1 else "map"
    ws = ROOT / "rag" / "data" / "workspaces" / workspace_id
    if not ws.exists():
        print(f"no workspace at {ws}", file=sys.stderr)
        return 1

    chunks = json.loads((ws / "chunks.json").read_text())
    videos = json.loads((ws / "videos.json").read_text())

    try:
        import rank_bm25, sentence_transformers   # noqa: F401
        retrieve_fn, retriever = None, "hybrid+rerank (full stack)"
    except ImportError:
        retrieve_fn = make_lexical_retriever(chunks)
        retriever = "lexical fallback (sentence-transformers/rank_bm25 unavailable)"

    print(f"workspace={workspace_id}  retriever={retriever}")

    results = []
    for question in QUESTIONS:
        print(f"  gating: {question}")
        result = find_clips(
            question, workspace_id,
            retrieve_fn=retrieve_fn,
            load_videos_fn=lambda w: videos,
        )
        result["retriever"] = retriever
        results.append(result)
        n = len(result["clips"])
        print(f"    -> {n} clip(s), {result['llm_calls']} LLM call(s)"
              + (f", ERRORS: {result['errors']}" if result["errors"] else ""))

    payload = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "workspace_id": workspace_id,
        "retriever": retriever,
        "videos": [{"video_id": v["video_id"], "title": v.get("title", ""),
                    "channel": v.get("channel", ""),
                    "duration_seconds": v.get("duration_seconds", 0)} for v in videos],
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))

    # Also emit a JS shim. fetch() of a sibling file fails under file://, so shipping the
    # data as a script tag means the demo works when opened straight from disk as well as
    # on Pages — no server, no CORS, no "why is it blank".
    js = OUT.with_name("data.js")
    js.write_text("window.CLIPGREP_DATA = " + json.dumps(payload, indent=2) + ";\n")

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(f"wrote {js.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
