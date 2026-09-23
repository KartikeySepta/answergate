# clipgrep Answer Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `cli.py clips <workspace> "<question>"` — returning only the timestamped clips that *answer* a question (not those that mention its topic), with conflicts flagged and skipped videos reported — plus the repo foundations and local-model accuracy measurement that make the positioning defensible.

**Architecture:** A new `rag/retrieval/clips.py` sits on top of the existing, unchanged retrieval stack (`hybrid_search` → `rerank`). Its new contribution is an **answer gate**: one batched LLM call that classifies each reranked chunk as `answers` / `mentions` / `unrelated` and returns a verbatim span, which is rejected unless it is genuinely contained in the chunk's text. A second batched call flags conflicting clips. Everything else is pure arithmetic. All decision logic lives in pure functions so it is testable offline; the heavy ML imports are deferred into function bodies so CI stays fast.

**Tech Stack:** Python 3.11, pytest, FastAPI, argparse. Existing: sentence-transformers (embeddings + cross-encoder), qdrant-client, rank-bm25, `core/llm.py` multi-provider wrapper (Gemini / Mistral / Grok / Ollama).

**Spec:** `docs/superpowers/specs/2026-09-24-clipgrep-v1-design.md` — read §1 (what was falsified and what survived), §3.2 (answer gate), §3.5 (local mode), §5 (risks), §6 (testing). This plan covers spec phases **0, 1, 2** only. Density (phase 3), the static demo (phase 4), and the rename (phase 5) are a follow-up plan.

## Global Constraints

Every task's requirements implicitly include these. Values are copied verbatim from the spec.

- **Verbatim guarantee:** an `answers` verdict is only accepted if its span is contained in the chunk's text after whitespace normalization. Otherwise the chunk is downgraded to `mentions` and excluded. The system never displays text a source did not say.
- **Cost budget: ~2 LLM calls per question** — one batched answer-gate call over all reranked chunks, one batched conflict call over the kept clips. Never one call per chunk or per pair.
- **Infrastructure failures must be distinguishable from real verdicts.** Follow `rag/knowledge/claim_clusterer.py:53-108`: an LLM or parse failure is reported as `errored`, never silently counted as a genuine negative verdict.
- **No module-level heavy imports in `clips.py`.** `sentence_transformers` and `qdrant_client` must be imported *inside* function bodies, following `rag/knowledge/claim_clusterer.py:47-50`. Module-level imports would pull torch into CI and into every pure-function test.
- **Tests run offline** — no network, no API key, no model downloads. Fakes are injected, following the `retrieve_fn` convention documented in `rag/evals/evaluate.py:40-44`.
- **Config lives only in `rag/core/config.py`.** Never hardcode a tunable in a caller. `CLIP_MAX_RETURNED = 5`, `CLIP_LINK_LEAD_SECONDS = 3`.
- **`clips` is a new command, not a change to `chat`.** `chat` returns prose; `clips` returns what to watch. Neither replaces the other.
- **Only `contradiction` raises a conflict flag in v1.** `partial_agreement` and `different_context` are deferred to v3.
- **License: MIT**, holder `Kartikey Septa`, year `2026`.
- **Test invocation:** `python3 -m pytest rag/tests/<file> -v`, run from the repo root. Test files begin with `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` then import `from core...` / `from retrieval...` — match `rag/tests/test_security.py:8-11` exactly.

---

### Task 1: Repo foundations — MIT license and CI

Without a license nobody may legally use the code, which makes every later task worthless to a company. Without CI the new pure functions are unverified. Both are independent of all engine work, so this task unblocks everything and depends on nothing.

**Files:**
- Create: `LICENSE`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: nothing.
- Produces: a green CI run on push and pull request, executing `python3 -m pytest rag/tests/ -v`. Later tasks add test files to `rag/tests/` and rely on CI picking them up with no workflow change.

- [ ] **Step 1: Create the MIT license**

Create `LICENSE`:

```
MIT License

Copyright (c) 2026 Kartikey Septa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Verify the existing tests pass locally before wiring CI**

Run:
```bash
python3 -m pip install pytest
python3 -m pytest rag/tests/ -v
```
Expected: all tests in `rag/tests/test_jobs.py` and `rag/tests/test_security.py` PASS.

If pytest reports collection errors, stop and report them — do not proceed to Step 3 with a red baseline.

Note: the existing two test files import only `core.jobs` and `core.security`, which use the standard library only. That is why CI does not need the heavy ML dependencies.

- [ ] **Step 3: Create the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      # Deliberately NOT installing requirements.txt. The offline test suite
      # imports only stdlib-backed modules, so pulling in torch and
      # sentence-transformers would add ~10 minutes per run for no coverage.
      # If a future test needs a heavy dependency, that is a signal the code
      # under test has a module-level import that should be deferred instead.
      - name: Install test dependencies
        run: python3 -m pip install pytest

      - name: Run offline test suite
        run: python3 -m pytest rag/tests/ -v
```

- [ ] **Step 4: Verify the workflow file is valid YAML**

Run:
```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```
Expected: `valid`

- [ ] **Step 5: Commit**

```bash
git add LICENSE .github/workflows/ci.yml
git commit -m "chore: add MIT license and offline CI

CI installs only pytest, not requirements.txt: the offline suite imports
stdlib-backed modules only, so pulling torch in would add ~10min per run
for zero coverage."
```

---

### Task 2: One-command startup — PO token sidecar and a working install path

`README.md:46` says the `bgutil-ytdlp-pot-provider` sidecar "must be running *every time* you scrape," but the untracked `docker-compose.yml` does not include it — so `docker compose up` produces a stack that 403s on download. Separately, `README.md:70-71` tells users to `pip install -r scraper/requirements.txt` and `-r rag/requirements.txt`, **neither of which exists** — only a root `requirements.txt` does. Both bugs break first-run for every new user, which the spec identifies as the binding constraint.

**Files:**
- Modify: `docker-compose.yml` (currently untracked; this task commits it)
- Modify: `README.md:61-85` (the Quick Start block)

**Interfaces:**
- Consumes: nothing.
- Produces: `docker compose up -d` brings up `rag-api` on 8000, `scraper-api` on 8001, and `pot-provider` on 4416. No later task depends on this programmatically.

- [ ] **Step 1: Verify the current compose file parses and inspect its indentation**

Run:
```bash
docker compose config >/dev/null && echo "parses OK" || echo "PARSE FAILURE"
```

The file's top-level keys are indented by two spaces. If this reports `PARSE FAILURE`, remove the two-space leading indentation from every line in Step 2 as well as making the additions. If it reports `parses OK`, leave the existing indentation style alone and match it in your additions.

- [ ] **Step 2: Add the PO token provider service**

Add this service to `docker-compose.yml`, matching the leading indentation of the existing `rag-api` and `scraper-api` entries:

```yaml
    pot-provider:
      # Generates a fresh, video-bound PO Token per request. Without this,
      # yt-dlp downloads intermittently 403 even when format listing works.
      # See README "Prerequisites".
      image: brainicism/bgutil-ytdlp-pot-provider
      container_name: bgutil-provider
      restart: unless-stopped
      ports:
        - "4416:4416"
```

Then add a dependency on it to the `scraper-api` service, so the sidecar is up before scraping can be attempted:

```yaml
      depends_on:
        - pot-provider
```

- [ ] **Step 3: Verify the compose file parses and lists three services**

Run:
```bash
docker compose config --services
```
Expected: three lines — `rag-api`, `scraper-api`, `pot-provider` (order may vary).

- [ ] **Step 4: Fix the broken install instructions in the README**

In `README.md`, replace these two lines inside the Quick Start block:

```
pip install -r scraper/requirements.txt
pip install -r rag/requirements.txt
```

with:

```
pip install -r requirements.txt
```

Then replace the Quick Start's step 3 (the single `docker run` line for `bgutil-provider`) with:

```bash
# 3. Start the PO token provider + APIs in one command
docker compose up -d
```

- [ ] **Step 5: Verify no stale references to the non-existent requirements files remain**

Run:
```bash
grep -rn "scraper/requirements.txt\|rag/requirements.txt" README.md rag/README.md || echo "no stale references"
```
Expected: `no stale references`.

If `rag/README.md:24` still says `pip install -r requirements.txt` in its own Setup section, that is correct as-is — it is relative to a different documented working directory. Leave it.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml README.md
git commit -m "fix: one-command startup and a working install path

- compose was missing the bgutil PO-token sidecar the README calls
  mandatory, so the stack 403'd on every download
- Quick Start pointed at scraper/requirements.txt and
  rag/requirements.txt, neither of which exists; only the root
  requirements.txt does"
```

---

### Task 3: Answer gate — prompt, parser, and the verbatim guarantee

This is the core of the product. Ordinary retrieval returns *topically relevant* chunks; the gate is what distinguishes a chunk that **answers** the question from one that merely **mentions** its topic, which is what makes the "9 videos mention this, none answer it" report possible.

All three functions here are pure — no network, no models — so they are fully testable offline.

**Files:**
- Modify: `rag/core/config.py` (append two constants)
- Create: `rag/retrieval/clips.py`
- Create: `rag/tests/test_clips.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, for Tasks 4-7:
  - `GATE_VERDICTS: set[str]` = `{"answers", "mentions", "unrelated"}`
  - `normalize_whitespace(text: str) -> str`
  - `build_answer_gate_prompt(question: str, chunks: list[dict]) -> str`
  - `parse_answer_gate_response(raw: str, chunks: list[dict]) -> tuple[list[dict], list[dict]]` returning `(verdicts, rejections)`, where each verdict is `{"chunk_id": str, "verdict": str, "span": str}` and each rejection is `{"reason": str, "chunk_id": str}`.
  - `rag/core/config.CLIP_MAX_RETURNED: int` = 5, `rag/core/config.CLIP_LINK_LEAD_SECONDS: int` = 3

- [ ] **Step 1: Add the config constants**

Append to `rag/core/config.py`:

```python
# Answer gate (clips). How many clips a single question returns. This also bounds
# the conflict-detection call: with 5 clips there are at most 10 pairs, checked in
# ONE batched call, which keeps a question at ~2 LLM calls total.
CLIP_MAX_RETURNED = 5

# Watch links start slightly early. Chunk timestamps are partly estimated by word
# position (see ingestion/chunker.py), so landing a few seconds before the span is
# far better UX than landing after the speaker has already said it.
CLIP_LINK_LEAD_SECONDS = 3
```

- [ ] **Step 2: Write the failing tests**

Create `rag/tests/test_clips.py`:

```python
"""
Tests for the answer gate — offline, no network, no LLM calls, no model loads.

  python3 -m pytest rag/tests/test_clips.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from retrieval.clips import (
    GATE_VERDICTS,
    build_answer_gate_prompt,
    normalize_whitespace,
    parse_answer_gate_response,
)

CHUNKS = [
    {"chunk_id": "vid1_c14", "video_id": "vid1", "channel": "@A",
     "text": "Water retention from creatine is intramuscular, not subcutaneous."},
    {"chunk_id": "vid2_c03", "video_id": "vid2", "channel": "@B",
     "text": "I take creatine every morning with my coffee."},
]


def _reply(verdicts):
    import json
    return json.dumps({"verdicts": verdicts})


# ─── WHITESPACE NORMALIZATION ─────────────────────────────────────────────────

def test_normalize_whitespace_collapses_runs():
    assert normalize_whitespace("a   b\n\tc") == "a b c"


def test_normalize_whitespace_strips_ends():
    assert normalize_whitespace("  hello  ") == "hello"


# ─── PROMPT ───────────────────────────────────────────────────────────────────

def test_prompt_includes_question_and_every_chunk_id():
    prompt = build_answer_gate_prompt("does creatine cause bloating?", CHUNKS)
    assert "does creatine cause bloating?" in prompt
    assert "vid1_c14" in prompt
    assert "vid2_c03" in prompt


def test_prompt_states_all_three_verdicts():
    prompt = build_answer_gate_prompt("q", CHUNKS)
    for verdict in GATE_VERDICTS:
        assert verdict in prompt


# ─── PARSER: STRUCTURE ────────────────────────────────────────────────────────

def test_parses_a_clean_answers_verdict():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers",
                   "span": "intramuscular, not subcutaneous"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert rejections == []
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "answers"
    assert verdicts[0]["chunk_id"] == "vid1_c14"


def test_strips_markdown_fences():
    raw = ('```json\n' + _reply([{"chunk_id": "vid2_c03", "verdict": "unrelated",
                                  "span": ""}]) + '\n```')
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "unrelated"


def test_unparseable_reply_raises():
    with pytest.raises(ValueError):
        parse_answer_gate_response("this is not json at all", CHUNKS)


# ─── PARSER: HALLUCINATION GUARDS ─────────────────────────────────────────────

def test_invented_chunk_id_is_rejected_not_returned():
    raw = _reply([{"chunk_id": "vid9_c99", "verdict": "answers", "span": "anything"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts == []
    assert len(rejections) == 1
    assert "vid9_c99" in rejections[0]["reason"]


def test_invalid_verdict_value_is_rejected():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "probably", "span": "x"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts == []
    assert len(rejections) == 1


def test_answers_with_span_not_in_chunk_is_downgraded_to_mentions():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers",
                   "span": "creatine is completely safe for your kidneys"}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert len(verdicts) == 1
    assert verdicts[0]["verdict"] == "mentions"
    assert len(rejections) == 1


def test_span_matching_tolerates_whitespace_differences():
    chunks = [{"chunk_id": "c1", "video_id": "v", "channel": "@A",
               "text": "Water  retention\nis intramuscular."}]
    raw = _reply([{"chunk_id": "c1", "verdict": "answers",
                   "span": "Water retention is intramuscular"}])
    verdicts, rejections = parse_answer_gate_response(raw, chunks)
    assert rejections == []
    assert verdicts[0]["verdict"] == "answers"


def test_answers_with_empty_span_is_downgraded():
    raw = _reply([{"chunk_id": "vid1_c14", "verdict": "answers", "span": ""}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert verdicts[0]["verdict"] == "mentions"
    assert len(rejections) == 1


def test_mentions_verdict_does_not_require_a_valid_span():
    raw = _reply([{"chunk_id": "vid2_c03", "verdict": "mentions", "span": ""}])
    verdicts, rejections = parse_answer_gate_response(raw, CHUNKS)
    assert rejections == []
    assert verdicts[0]["verdict"] == "mentions"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'retrieval.clips'`

- [ ] **Step 4: Write the implementation**

Create `rag/retrieval/clips.py`:

```python
"""
ANSWER GATE — the difference between "relevant to your topic" and "answers your question".

Ordinary retrieval returns topically similar chunks. That is why a summarizer can never
tell you a video is padding: it has no notion of a chunk failing to answer. The gate adds
one batched LLM call that labels each reranked chunk `answers` / `mentions` / `unrelated`,
which is what makes "9 videos mention creatine, none answer this" possible.

Two guards, both mirroring knowledge/claim_extractor.py's evidence validation:
  1. A verdict naming a chunk_id we never sent is discarded outright.
  2. An `answers` verdict must quote a span that is really in the chunk. If it isn't, the
     chunk is downgraded to `mentions`. We never display text a source did not say.

IMPORTANT: heavy imports (sentence_transformers via the reranker, qdrant_client via the
vector store) are deliberately deferred into function bodies — same pattern as
knowledge/claim_clusterer.py's _call_gemini. Everything above find_clips() is pure and
testable with no models, no network, and no API key.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GATE_VERDICTS = {"answers", "mentions", "unrelated"}


def normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip the ends.

    Models reproduce quotes with different line breaks and spacing than the source.
    Normalizing both sides before the containment check keeps the verbatim guarantee
    meaningful (same words, same order) without failing on cosmetic differences.
    """
    return " ".join(text.split())


def build_answer_gate_prompt(question: str, chunks: list[dict]) -> str:
    """One prompt covering EVERY candidate chunk — one call, not one per chunk."""
    blocks = "\n\n".join(
        f'[chunk_id: {c["chunk_id"]}]\n"{c["text"]}"' for c in chunks
    )
    return f"""You decide, for each excerpt below, whether it ANSWERS a specific question
or merely MENTIONS the topic. This distinction is the entire point — be strict.

QUESTION: "{question}"

Label each excerpt with exactly one verdict:
- "answers"   — the excerpt contains information that actually answers the question
- "mentions"  — the excerpt is about the topic but does not answer the question
- "unrelated" — the excerpt is not about the question's topic at all

For "answers" ONLY, also return "span": the shortest run of text COPIED WORD FOR WORD
from that excerpt that does the answering. Do not paraphrase, do not correct, do not
summarize. If you cannot copy an exact span, the verdict is "mentions", not "answers".
For "mentions" and "unrelated", use an empty span.

Return ONLY JSON, no markdown fences:
{{"verdicts": [{{"chunk_id": "...", "verdict": "...", "span": "..."}}]}}

Use only the chunk_id values given below. Include every excerpt exactly once.

EXCERPTS:
{blocks}
"""


def _strip_fences(raw: str) -> str:
    """Drop ```json ... ``` wrappers. Same handling as claim_clusterer.adjudicate_merge."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def parse_answer_gate_response(raw: str, chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate the gate's reply against the chunks we actually sent.

    Returns (verdicts, rejections). A rejection is never silently dropped — callers
    surface the count so a degraded model is visible rather than looking like a corpus
    with nothing to say.

    Raises ValueError if the reply is not parseable JSON at all. That is an infrastructure
    failure, not a verdict, and the caller must treat it as such (see Global Constraints).
    """
    try:
        parsed = json.loads(_strip_fences(raw))
    except Exception as e:
        raise ValueError(f"unparseable answer-gate reply: {e}")

    text_by_id = {c["chunk_id"]: c["text"] for c in chunks}
    verdicts: list[dict] = []
    rejections: list[dict] = []

    for item in parsed.get("verdicts", []):
        chunk_id = item.get("chunk_id", "")
        verdict = item.get("verdict", "")
        span = (item.get("span") or "").strip()

        # Guard 1: a chunk_id we never sent means the model invented a source.
        if chunk_id not in text_by_id:
            rejections.append({
                "reason": f"unknown chunk_id '{chunk_id}' (not in the candidates sent)",
                "chunk_id": chunk_id,
            })
            continue

        if verdict not in GATE_VERDICTS:
            rejections.append({
                "reason": f"invalid verdict '{verdict}'",
                "chunk_id": chunk_id,
            })
            continue

        # Guard 2: an "answers" claim must quote the chunk, not paraphrase it.
        if verdict == "answers":
            if not span:
                rejections.append({
                    "reason": "verdict 'answers' with an empty span; downgraded to 'mentions'",
                    "chunk_id": chunk_id,
                })
                verdict = "mentions"
            elif normalize_whitespace(span) not in normalize_whitespace(text_by_id[chunk_id]):
                rejections.append({
                    "reason": "span is not verbatim in the chunk; downgraded to 'mentions'",
                    "chunk_id": chunk_id,
                })
                verdict = "mentions"

        verdicts.append({"chunk_id": chunk_id, "verdict": verdict, "span": span})

    return verdicts, rejections
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: all 12 tests PASS.

- [ ] **Step 6: Verify the module imports without any heavy dependency**

Run:
```bash
python3 -c "
import sys; sys.path.insert(0, 'rag')
import retrieval.clips
assert 'torch' not in sys.modules, 'torch got imported — a heavy import leaked to module level'
assert 'qdrant_client' not in sys.modules, 'qdrant_client got imported at module level'
print('clean import OK')
"
```
Expected: `clean import OK`

- [ ] **Step 7: Commit**

```bash
git add rag/retrieval/clips.py rag/tests/test_clips.py rag/core/config.py
git commit -m "feat(clips): answer gate prompt, parser, and verbatim guarantee

An 'answers' verdict is only accepted if its span is really in the chunk
(whitespace-normalized); otherwise it degrades to 'mentions'. Same
discipline as claim_extractor's evidence chunk_id validation."
```

---

### Task 4: Watch links and the skip report

These produce the two most quotable parts of the output — the clickable timestamp and "3h 51m saved". Both are pure arithmetic and both have off-by-one risks that would be embarrassing in a demo.

**Files:**
- Modify: `rag/retrieval/clips.py` (append)
- Modify: `rag/tests/test_clips.py` (append)

**Interfaces:**
- Consumes: `CLIP_LINK_LEAD_SECONDS` from `rag/core/config.py` (Task 3).
- Produces, for Tasks 6-8:
  - `build_watch_url(video_id: str, start_seconds: float, lead: int | None = None) -> str`
  - `build_skip_report(all_videos: list[dict], answering_video_ids: set[str]) -> dict` returning `{"video_count": int, "total_seconds": int, "video_ids": list[str]}`
  - `format_duration(seconds: int) -> str` returning e.g. `"3h 51m"`, `"12m"`, `"0m"`

- [ ] **Step 1: Write the failing tests**

Append to `rag/tests/test_clips.py`:

```python
# ─── WATCH LINKS ──────────────────────────────────────────────────────────────

from retrieval.clips import build_skip_report, build_watch_url, format_duration


def test_watch_url_starts_three_seconds_early():
    assert build_watch_url("abc123", 1170.0) == "https://youtu.be/abc123?t=1167"


def test_watch_url_truncates_fractional_seconds():
    assert build_watch_url("abc123", 1170.9) == "https://youtu.be/abc123?t=1167"


def test_watch_url_clamps_at_zero_instead_of_going_negative():
    assert build_watch_url("abc123", 1.0) == "https://youtu.be/abc123?t=0"


def test_watch_url_clamps_at_zero_for_a_zero_start():
    assert build_watch_url("abc123", 0.0) == "https://youtu.be/abc123?t=0"


def test_watch_url_lead_is_overridable():
    assert build_watch_url("abc123", 100.0, lead=0) == "https://youtu.be/abc123?t=100"


# ─── SKIP REPORT ──────────────────────────────────────────────────────────────

VIDEOS = [
    {"video_id": "v1", "duration_seconds": 1440},
    {"video_id": "v2", "duration_seconds": 600},
    {"video_id": "v3", "duration_seconds": 900},
]


def test_skip_report_counts_videos_with_no_answering_clip():
    report = build_skip_report(VIDEOS, {"v1"})
    assert report["video_count"] == 2
    assert report["total_seconds"] == 1500
    assert report["video_ids"] == ["v2", "v3"]


def test_skip_report_is_empty_when_every_video_answered():
    report = build_skip_report(VIDEOS, {"v1", "v2", "v3"})
    assert report["video_count"] == 0
    assert report["total_seconds"] == 0
    assert report["video_ids"] == []


def test_skip_report_treats_missing_duration_as_zero():
    videos = [{"video_id": "v1"}, {"video_id": "v2", "duration_seconds": None}]
    report = build_skip_report(videos, set())
    assert report["video_count"] == 2
    assert report["total_seconds"] == 0


def test_format_duration_uses_hours_and_minutes():
    assert format_duration(13860) == "3h 51m"


def test_format_duration_omits_hours_under_one_hour():
    assert format_duration(720) == "12m"


def test_format_duration_handles_zero():
    assert format_duration(0) == "0m"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_skip_report' from 'retrieval.clips'`

- [ ] **Step 3: Write the implementation**

Append to `rag/retrieval/clips.py`:

```python
def build_watch_url(video_id: str, start_seconds: float, lead: int | None = None) -> str:
    """A YouTube link that seeks a few seconds BEFORE the span.

    Chunk timestamps are partly estimated by word position (ingestion/chunker.py), so they
    drift. Landing slightly early means the viewer hears the lead-in; landing late means
    they missed the answer and think the tool is broken. Clamped at 0 — a negative t would
    be ignored by YouTube and silently start the video from the beginning.
    """
    from core.config import CLIP_LINK_LEAD_SECONDS
    if lead is None:
        lead = CLIP_LINK_LEAD_SECONDS
    t = max(0, int(start_seconds) - lead)
    return f"https://youtu.be/{video_id}?t={t}"


def build_skip_report(all_videos: list[dict], answering_video_ids: set[str]) -> dict:
    """Which videos contributed nothing, and how much runtime that is.

    This is the honest inverse of the answer: not just "here is your answer" but "here is
    what you can safely not watch." A missing or null duration counts as 0 rather than
    raising — an un-scraped duration should not take down a query.
    """
    skipped = [v for v in all_videos if v["video_id"] not in answering_video_ids]
    return {
        "video_count": len(skipped),
        "total_seconds": sum(int(v.get("duration_seconds") or 0) for v in skipped),
        "video_ids": [v["video_id"] for v in skipped],
    }


def format_duration(seconds: int) -> str:
    """13860 -> '3h 51m'. Minutes only under an hour, so short corpora don't read as '0h 12m'."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: all tests PASS.

Note: `format_duration(13860)` must produce exactly `"3h 51m"`. 13860 seconds is 3 hours and 51 minutes, so the `{minutes:02d}` zero-padding yields `51`. If a test fails because of padding on a single-digit minute value, fix the *test* expectation to match two-digit padding — do not remove the padding, because unpadded minutes read ambiguously next to hours.

- [ ] **Step 5: Commit**

```bash
git add rag/retrieval/clips.py rag/tests/test_clips.py
git commit -m "feat(clips): watch links with early-seek bias and the skip report

Links seek 3s early and clamp at 0: chunk timestamps are estimated by
word position, and landing after the answer reads as a broken tool."
```

---

### Task 5: Conflict detection between returned clips

When two clips answer the same question differently, saying so is the honest thing to do. The spec (§3.2) explains why this cannot reuse `synthesizer.build_relationship_prompt`: that function returns one label for a whole group and cannot say *which pair* conflicts, and calling it pairwise would cost 10 LLM calls instead of 1.

**Files:**
- Modify: `rag/retrieval/clips.py` (append)
- Modify: `rag/tests/test_clips.py` (append)

**Interfaces:**
- Consumes: `_strip_fences` from Task 3.
- Produces, for Tasks 6-8:
  - `build_conflict_prompt(clips: list[dict]) -> str` — clips are 1-indexed by position in the list
  - `parse_conflict_response(raw: str, clip_count: int) -> list[tuple[int, int]]` — returns sorted, deduplicated, validated 1-based index pairs

- [ ] **Step 1: Write the failing tests**

Append to `rag/tests/test_clips.py`:

```python
# ─── CONFLICT DETECTION ───────────────────────────────────────────────────────

from retrieval.clips import build_conflict_prompt, parse_conflict_response

CLIPS = [
    {"chunk_id": "vid1_c14", "channel": "@A", "span": "retention is intramuscular"},
    {"chunk_id": "vid2_c03", "channel": "@B", "span": "it makes you look puffy"},
]


def test_conflict_prompt_numbers_clips_from_one():
    prompt = build_conflict_prompt(CLIPS)
    assert "[1]" in prompt
    assert "[2]" in prompt
    assert "[0]" not in prompt


def test_conflict_prompt_includes_each_span():
    prompt = build_conflict_prompt(CLIPS)
    assert "retention is intramuscular" in prompt
    assert "it makes you look puffy" in prompt


def test_parses_a_conflicting_pair():
    assert parse_conflict_response('{"conflicts": [[1, 2]]}', 2) == [(1, 2)]


def test_parses_an_empty_conflict_list():
    assert parse_conflict_response('{"conflicts": []}', 2) == []


def test_conflict_pairs_are_normalized_to_ascending_order():
    assert parse_conflict_response('{"conflicts": [[2, 1]]}', 2) == [(1, 2)]


def test_duplicate_conflict_pairs_are_deduplicated():
    assert parse_conflict_response('{"conflicts": [[1, 2], [2, 1]]}', 2) == [(1, 2)]


def test_out_of_range_index_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1, 9]]}', 2) == []


def test_zero_index_is_discarded_because_clips_are_one_based():
    assert parse_conflict_response('{"conflicts": [[0, 1]]}', 2) == []


def test_self_pair_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1, 1]]}', 2) == []


def test_malformed_pair_shape_is_discarded():
    assert parse_conflict_response('{"conflicts": [[1], [1, 2, 3], "nope"]}', 3) == []


def test_unparseable_conflict_reply_raises():
    with pytest.raises(ValueError):
        parse_conflict_response("not json", 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_conflict_prompt' from 'retrieval.clips'`

- [ ] **Step 3: Write the implementation**

Append to `rag/retrieval/clips.py`:

```python
def build_conflict_prompt(clips: list[dict]) -> str:
    """Ask, in ONE call, which of these clips actually contradict each other.

    Deliberately NOT knowledge/synthesizer.build_relationship_prompt: that returns a single
    label for a whole group, so it cannot say which PAIR conflicts, and running it pairwise
    over 5 clips would cost 10 calls instead of 1.

    Clips are numbered from 1 to match what the user sees in the rendered output.
    """
    blocks = "\n".join(
        f'[{i}] ({c.get("channel", "unknown")}) "{c.get("span", "")}"'
        for i, c in enumerate(clips, start=1)
    )
    return f"""These numbered excerpts all answer the same question. Identify only the pairs
that GENUINELY CONTRADICT each other — asserting incompatible things about the same
situation.

Do NOT report a pair as conflicting when they:
- agree, or mostly agree with minor differences
- describe different situations, populations, or timeframes (both can be true at once)
- are simply about different aspects of the topic

Return ONLY JSON, no markdown fences. Use the bracket numbers shown:
{{"conflicts": [[1, 2]]}}

If nothing genuinely contradicts, return {{"conflicts": []}}.

EXCERPTS:
{blocks}
"""


def parse_conflict_response(raw: str, clip_count: int) -> list[tuple[int, int]]:
    """Validate conflict pairs against the clips we actually sent.

    Every index must refer to a real clip — an invented index is discarded rather than
    rendered, mirroring synthesizer.parse_relationship_response's valid_claim_ids check.
    Pairs are normalized ascending and deduplicated so (2,1) and (1,2) are one conflict.

    Raises ValueError on unparseable JSON — an infrastructure failure, not a verdict.
    """
    try:
        parsed = json.loads(_strip_fences(raw))
    except Exception as e:
        raise ValueError(f"unparseable conflict reply: {e}")

    seen: set[tuple[int, int]] = set()
    for pair in parsed.get("conflicts", []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        try:
            a, b = int(pair[0]), int(pair[1])
        except (TypeError, ValueError):
            continue
        if a == b:
            continue
        if not (1 <= a <= clip_count and 1 <= b <= clip_count):
            continue
        seen.add((min(a, b), max(a, b)))

    return sorted(seen)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rag/retrieval/clips.py rag/tests/test_clips.py
git commit -m "feat(clips): batched conflict detection with index validation

One call over all kept clips returning which pairs conflict. Cannot reuse
synthesizer.build_relationship_prompt: it returns one label per group, so
it can't identify a pair, and pairwise would be 10 calls not 1."
```

---

### Task 6: Orchestration — `find_clips()`

Wires retrieval, the gate, conflict detection, and the skip report into one result. Retrieval and LLM access are injected so the whole flow is testable offline, following the `retrieve_fn` convention already documented at `rag/evals/evaluate.py:40-44`.

**Files:**
- Modify: `rag/retrieval/clips.py` (append)
- Modify: `rag/tests/test_clips.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 3-5.
- Produces, for Tasks 7-9:
  `find_clips(question: str, workspace_id: str, retrieve_fn=None, generate_fn=None, load_videos_fn=None) -> dict`

  Returns:
  ```python
  {"question": str, "workspace_id": str, "provider": str,
   "clips": [{"rank": int, "chunk_id": str, "video_id": str, "video_title": str,
              "channel": str, "start_seconds": float, "end_seconds": float,
              "is_estimated": bool, "span": str, "watch_url": str,
              "conflicts_with": list[int]}],
   "skipped": {"video_count": int, "total_seconds": int, "video_ids": list[str]},
   "llm_calls": int, "rejections": list[dict], "errors": list[str]}
  ```

- [ ] **Step 1: Write the failing tests**

Append to `rag/tests/test_clips.py`:

```python
# ─── ORCHESTRATION ────────────────────────────────────────────────────────────

from retrieval.clips import find_clips

# rerank_score is present because real retrieval always supplies it (reranker.py:48) and
# because it is the PRIMARY sort key — fixtures without it would let the is_estimated
# tie-break silently reorder results and hide a ranking bug.
RETRIEVED = [
    {"chunk_id": "v1_c1", "video_id": "v1", "video_title": "T1", "channel": "@A",
     "start_seconds": 1170.0, "end_seconds": 1218.0, "is_estimated": True,
     "rerank_score": 0.91,
     "text": "Water retention from creatine is intramuscular, not subcutaneous."},
    {"chunk_id": "v2_c1", "video_id": "v2", "video_title": "T2", "channel": "@B",
     "start_seconds": 482.0, "end_seconds": 554.0, "is_estimated": False,
     "rerank_score": 0.80,
     "text": "Creatine makes you look puffy and bloated all over."},
    {"chunk_id": "v3_c1", "video_id": "v3", "video_title": "T3", "channel": "@C",
     "start_seconds": 10.0, "end_seconds": 70.0, "is_estimated": False,
     "rerank_score": 0.42,
     "text": "I keep my creatine tub next to the blender."},
]

ALL_VIDEOS = [
    {"video_id": "v1", "duration_seconds": 1440},
    {"video_id": "v2", "duration_seconds": 600},
    {"video_id": "v3", "duration_seconds": 900},
    {"video_id": "v4", "duration_seconds": 1200},
]


def _fake_generate(gate_reply, conflict_reply='{"conflicts": []}'):
    """Returns a generate_fn that answers the gate call first, then the conflict call."""
    calls = []

    def generate_fn(prompt, task=None):
        calls.append(task)
        return gate_reply if len(calls) == 1 else conflict_reply

    generate_fn.calls = calls
    return generate_fn


GATE_TWO_ANSWERS = json.dumps({"verdicts": [
    {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
    {"chunk_id": "v2_c1", "verdict": "answers", "span": "puffy and bloated all over"},
    {"chunk_id": "v3_c1", "verdict": "mentions", "span": ""},
]})


def _run(gate_reply, conflict_reply='{"conflicts": []}'):
    return find_clips(
        "does creatine cause bloating?", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=_fake_generate(gate_reply, conflict_reply),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )


def test_only_answering_chunks_become_clips():
    result = _run(GATE_TWO_ANSWERS)
    assert [c["chunk_id"] for c in result["clips"]] == ["v1_c1", "v2_c1"]


def test_clips_are_ranked_from_one():
    result = _run(GATE_TWO_ANSWERS)
    assert [c["rank"] for c in result["clips"]] == [1, 2]


def test_clip_carries_a_watch_url_seeking_early():
    result = _run(GATE_TWO_ANSWERS)
    assert result["clips"][0]["watch_url"] == "https://youtu.be/v1?t=1167"


def test_relevance_outranks_timestamp_quality():
    """is_estimated is a TIE-BREAK, never a primary sort.

    v1_c1 has estimated timestamps but a higher rerank_score than v2_c1. It must still
    rank first — demoting a more relevant clip because its timestamp is approximate would
    make the tool worse at its actual job.
    """
    result = _run(GATE_TWO_ANSWERS)
    assert result["clips"][0]["chunk_id"] == "v1_c1"
    assert result["clips"][0]["is_estimated"] is True


def test_estimated_loses_only_on_an_exact_score_tie():
    tied = [
        {**RETRIEVED[0], "rerank_score": 0.80},   # estimated, tied score
        {**RETRIEVED[1], "rerank_score": 0.80},   # exact, tied score
    ]
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
        {"chunk_id": "v2_c1", "verdict": "answers", "span": "puffy and bloated all over"},
    ]})
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: tied,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["clips"][0]["chunk_id"] == "v2_c1", "exact timestamps win an exact tie"


def test_mentioned_but_not_answering_video_counts_as_skipped():
    result = _run(GATE_TWO_ANSWERS)
    # v3 only mentions; v4 never retrieved. Both are skippable.
    assert result["skipped"]["video_count"] == 2
    assert sorted(result["skipped"]["video_ids"]) == ["v3", "v4"]
    assert result["skipped"]["total_seconds"] == 2100


def test_uses_two_llm_calls_when_there_are_multiple_clips():
    result = _run(GATE_TWO_ANSWERS)
    assert result["llm_calls"] == 2


def test_skips_the_conflict_call_with_fewer_than_two_clips():
    gate = json.dumps({"verdicts": [
        {"chunk_id": "v1_c1", "verdict": "answers", "span": "intramuscular, not subcutaneous"},
        {"chunk_id": "v2_c1", "verdict": "mentions", "span": ""},
        {"chunk_id": "v3_c1", "verdict": "unrelated", "span": ""},
    ]})
    result = _run(gate)
    assert len(result["clips"]) == 1
    assert result["llm_calls"] == 1


def test_conflicts_are_recorded_on_both_clips():
    result = _run(GATE_TWO_ANSWERS, '{"conflicts": [[1, 2]]}')
    assert result["clips"][0]["conflicts_with"] == [2]
    assert result["clips"][1]["conflicts_with"] == [1]


def test_no_clips_when_nothing_answers():
    gate = json.dumps({"verdicts": [
        {"chunk_id": c["chunk_id"], "verdict": "mentions", "span": ""} for c in RETRIEVED
    ]})
    result = _run(gate)
    assert result["clips"] == []
    assert result["skipped"]["video_count"] == 4


def test_gate_infra_failure_is_reported_not_silently_empty():
    def exploding_generate(prompt, task=None):
        raise RuntimeError("all providers exhausted")

    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=exploding_generate,
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert result["clips"] == []
    assert result["errors"], "an infra failure must be surfaced, not look like 'nothing answers'"


def test_conflict_failure_does_not_discard_the_clips():
    def generate_fn(prompt, task=None):
        if "CONTRADICT" in prompt.upper():
            raise RuntimeError("rate limited")
        return GATE_TWO_ANSWERS

    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: RETRIEVED,
        generate_fn=generate_fn,
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert len(result["clips"]) == 2
    assert result["errors"]


def test_respects_the_clip_cap():
    from core.config import CLIP_MAX_RETURNED
    many = [
        {"chunk_id": f"v{i}_c1", "video_id": f"v{i}", "video_title": "T", "channel": "@X",
         "start_seconds": 10.0, "end_seconds": 70.0, "is_estimated": False,
         "rerank_score": 1.0 - (i / 100.0),
         "text": f"answer number {i} here"}
        for i in range(CLIP_MAX_RETURNED + 3)
    ]
    gate = json.dumps({"verdicts": [
        {"chunk_id": c["chunk_id"], "verdict": "answers", "span": c["text"]} for c in many
    ]})
    result = find_clips(
        "q", "fitness",
        retrieve_fn=lambda q, w: many,
        generate_fn=_fake_generate(gate),
        load_videos_fn=lambda w: ALL_VIDEOS,
    )
    assert len(result["clips"]) == CLIP_MAX_RETURNED
```

Add `import json` to the top of the test file if it is not already there (Task 3's `_reply` helper imports it locally; the orchestration tests need it at module scope).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_clips' from 'retrieval.clips'`

- [ ] **Step 3: Write the implementation**

Append to `rag/retrieval/clips.py`:

```python
def _default_retrieve(question: str, workspace_id: str) -> list[dict]:
    """Real retrieval: existing hybrid search + cross-encoder rerank, unchanged.

    Imported HERE rather than at module scope so the pure functions above stay importable
    without torch or qdrant — see this module's docstring.
    """
    from core.config import RERANK_KEEP_TOP, VECTOR_TOP_K
    from retrieval.hybrid import hybrid_search
    from retrieval.reranker import rerank

    fused = hybrid_search(question, workspace_id=workspace_id, top_k=VECTOR_TOP_K)
    return rerank(question, fused, top_k=RERANK_KEEP_TOP)


def _default_generate(prompt: str, task: str | None = None) -> str:
    from core.llm import generate_content
    return generate_content(prompt, task=task)


def _default_load_videos(workspace_id: str) -> list[dict]:
    from core.config import WORKSPACES_DIR
    path = Path(WORKSPACES_DIR) / workspace_id / "videos.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def find_clips(
    question: str,
    workspace_id: str,
    retrieve_fn=None,
    generate_fn=None,
    load_videos_fn=None,
) -> dict:
    """Return only the clips that ANSWER the question, plus what you can skip.

    retrieve_fn / generate_fn / load_videos_fn are injectable so this is testable with no
    network and no models — the same pattern evals/evaluate.py uses for retrieve_fn.

    Cost: 2 LLM calls (gate + conflicts), or 1 when fewer than two clips survive the gate.

    An infrastructure failure is recorded in `errors` and never rendered as "nothing
    answers your question" — those two outcomes look identical to a user and must not be
    conflated (see knowledge/claim_clusterer.py:53-108 for the same distinction).
    """
    from core.config import CLIP_MAX_RETURNED

    retrieve_fn = retrieve_fn or _default_retrieve
    generate_fn = generate_fn or _default_generate
    load_videos_fn = load_videos_fn or _default_load_videos

    errors: list[str] = []
    rejections: list[dict] = []
    llm_calls = 0

    candidates = retrieve_fn(question, workspace_id)
    all_videos = load_videos_fn(workspace_id)

    # ─── The gate: one batched call over every candidate ───────────────────────
    verdicts = []
    if candidates:
        try:
            raw = generate_fn(build_answer_gate_prompt(question, candidates), task="gate")
            llm_calls += 1
            verdicts, rejections = parse_answer_gate_response(raw, candidates)
        except Exception as e:
            errors.append(f"answer gate failed (no verdicts obtained): {e}")

    answering_ids = {v["chunk_id"] for v in verdicts if v["verdict"] == "answers"}
    span_by_id = {v["chunk_id"]: v["span"] for v in verdicts}

    kept = [c for c in candidates if c["chunk_id"] in answering_ids]
    # Relevance is PRIMARY: the cross-encoder score decides the order. is_estimated is only
    # a TIE-BREAK, so an exactly-anchored clip wins over an estimated one of equal
    # relevance — it must never outrank a genuinely more relevant clip (spec §5.1).
    kept.sort(key=lambda c: (-(c.get("rerank_score") or 0.0), bool(c.get("is_estimated"))))
    kept = kept[:CLIP_MAX_RETURNED]

    clips = [
        {
            "rank": i,
            "chunk_id": c["chunk_id"],
            "video_id": c["video_id"],
            "video_title": c.get("video_title", ""),
            "channel": c.get("channel", ""),
            "start_seconds": c.get("start_seconds"),
            "end_seconds": c.get("end_seconds"),
            "is_estimated": bool(c.get("is_estimated")),
            "span": span_by_id.get(c["chunk_id"], ""),
            "watch_url": build_watch_url(c["video_id"], c.get("start_seconds") or 0),
            "conflicts_with": [],
        }
        for i, c in enumerate(kept, start=1)
    ]

    # ─── Conflicts: one batched call, only worth making with 2+ clips ──────────
    if len(clips) >= 2:
        try:
            raw = generate_fn(build_conflict_prompt(clips), task="gate")
            llm_calls += 1
            for a, b in parse_conflict_response(raw, len(clips)):
                clips[a - 1]["conflicts_with"].append(b)
                clips[b - 1]["conflicts_with"].append(a)
        except Exception as e:
            # A conflict-check failure must not discard perfectly good clips.
            errors.append(f"conflict check unavailable: {e}")

    return {
        "question": question,
        "workspace_id": workspace_id,
        "provider": os.environ.get("LLM_BACKEND", "auto"),
        "clips": clips,
        "skipped": build_skip_report(all_videos, {c["video_id"] for c in clips}),
        "llm_calls": llm_calls,
        "rejections": rejections,
        "errors": errors,
    }
```

Add `import os` to the imports at the top of `rag/retrieval/clips.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Re-verify no heavy import leaked**

Run:
```bash
python3 -c "
import sys; sys.path.insert(0, 'rag')
import retrieval.clips
assert 'torch' not in sys.modules and 'qdrant_client' not in sys.modules
print('still clean')
"
```
Expected: `still clean`

- [ ] **Step 6: Commit**

```bash
git add rag/retrieval/clips.py rag/tests/test_clips.py
git commit -m "feat(clips): orchestrate gate, conflicts, and skip report

Injectable retrieve/generate/load_videos keeps the whole flow testable
offline. An infra failure lands in errors[] rather than masquerading as
'nothing answers your question' — those must never look the same."
```

---

### Task 7: CLI command and terminal renderer

**Files:**
- Modify: `rag/cli.py` (add `cmd_clips` near `cmd_chat` at line 332; add a subparser near line 756)
- Modify: `rag/tests/test_clips.py` (append renderer tests)

**Interfaces:**
- Consumes: `find_clips` (Task 6), `format_duration` (Task 4).
- Produces: `render_clips(result: dict) -> str` in `rag/retrieval/clips.py`, and a working `python3 cli.py clips <workspace> "<question>" [--json]`.

- [ ] **Step 1: Write the failing renderer tests**

Append to `rag/tests/test_clips.py`:

```python
# ─── RENDERER ─────────────────────────────────────────────────────────────────

from retrieval.clips import render_clips

RESULT = {
    "question": "does creatine cause bloating?",
    "workspace_id": "fitness",
    "provider": "gemini",
    "clips": [
        {"rank": 1, "chunk_id": "v1_c1", "video_id": "v1", "video_title": "T1",
         "channel": "@A", "start_seconds": 1170.0, "end_seconds": 1218.0,
         "is_estimated": True, "span": "intramuscular, not subcutaneous",
         "watch_url": "https://youtu.be/v1?t=1167", "conflicts_with": [2]},
        {"rank": 2, "chunk_id": "v2_c1", "video_id": "v2", "video_title": "T2",
         "channel": "@B", "start_seconds": 482.0, "end_seconds": 554.0,
         "is_estimated": False, "span": "puffy and bloated all over",
         "watch_url": "https://youtu.be/v2?t=479", "conflicts_with": [1]},
    ],
    "skipped": {"video_count": 9, "total_seconds": 13860, "video_ids": []},
    "llm_calls": 2, "rejections": [], "errors": [],
}


def test_render_shows_channel_and_span():
    out = render_clips(RESULT)
    assert "@A" in out
    assert "intramuscular, not subcutaneous" in out


def test_render_shows_the_watch_url():
    assert "https://youtu.be/v1?t=1167" in render_clips(RESULT)


def test_render_marks_estimated_timestamps_with_a_tilde():
    out = render_clips(RESULT)
    assert "~19:30" in out


def test_render_does_not_mark_exact_timestamps():
    out = render_clips(RESULT)
    assert "~8:02" not in out
    assert "8:02" in out


def test_render_flags_conflicts():
    assert "CONFLICTS" in render_clips(RESULT).upper()


def test_render_reports_time_saved():
    out = render_clips(RESULT)
    assert "9" in out
    assert "3h 51m" in out


def test_render_says_so_when_nothing_answers():
    empty = {**RESULT, "clips": []}
    assert "no clip" in render_clips(empty).lower()


def test_render_surfaces_errors_distinctly_from_no_answers():
    failed = {**RESULT, "clips": [], "errors": ["answer gate failed: boom"]}
    out = render_clips(failed).lower()
    assert "error" in out or "failed" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_clips'`

- [ ] **Step 3: Implement the renderer**

Append to `rag/retrieval/clips.py`:

```python
def render_clips(result: dict) -> str:
    """Plain-text output. No rich dependency, so it works when piped or in CI."""
    from retrieval.context import format_timestamp

    lines: list[str] = []
    clips = result["clips"]
    skipped = result["skipped"]

    if result["errors"]:
        lines.append("ERRORS (results below may be incomplete):")
        for err in result["errors"]:
            lines.append(f"  ! {err}")
        lines.append("")

    if not clips:
        lines.append(f'No clip in this workspace answers: "{result["question"]}"')
        if not result["errors"]:
            lines.append("The topic may be mentioned without being answered.")
        return "\n".join(lines)

    lines.append(f'{len(clips)} clip(s) answer: "{result["question"]}"')
    lines.append("")

    for c in clips:
        mark = "~" if c["is_estimated"] else ""
        start = format_timestamp(c["start_seconds"])
        end = format_timestamp(c["end_seconds"])
        lines.append(f'[{c["rank"]}] {c["channel"]} — {c["video_title"]}')
        lines.append(f'    {mark}{start} → {mark}{end}   {c["watch_url"]}')
        lines.append(f'    "{c["span"]}"')
        if c["conflicts_with"]:
            others = ", ".join(f"[{n}]" for n in c["conflicts_with"])
            lines.append(f"    ! CONFLICTS with {others}")
        lines.append("")

    if skipped["video_count"]:
        saved = format_duration(skipped["total_seconds"])
        lines.append(f'{skipped["video_count"]} video(s) had no answering clip '
                     f'— {saved} you can skip')

    if result["rejections"]:
        lines.append(f'({len(result["rejections"])} model output(s) rejected by validation)')

    return "\n".join(lines)
```

Note: `format_timestamp` lives in `rag/retrieval/context.py:26` and is pure (no heavy imports), so importing it inside the function is safe for the offline tests.

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest rag/tests/test_clips.py -v`
Expected: all tests PASS. `format_timestamp(1170.0)` returns `"19:30"` and `format_timestamp(482.0)` returns `"8:02"`.

- [ ] **Step 5: Add the CLI command handler**

In `rag/cli.py`, add this function immediately before `def cmd_chat(args):` at line 332:

```python
def cmd_clips(args):
    """Return only the clips that ANSWER a question, not those that mention the topic."""
    from retrieval.clips import find_clips, render_clips

    result = find_clips(args.question, workspace_id=args.workspace_id)

    if args.json:
        import json as _json
        print(_json.dumps(result, indent=2))
    else:
        print(render_clips(result))
```

- [ ] **Step 6: Register the subparser**

In `rag/cli.py`, add immediately after the `p_chat.set_defaults(func=cmd_chat)` line (around line 761):

```python
    p_clips = subparsers.add_parser(
        "clips", help="Find the clips that ANSWER a question (not just mention it)")
    p_clips.add_argument("workspace_id")
    p_clips.add_argument("question")
    p_clips.add_argument("--json", action="store_true", help="Emit raw JSON")
    p_clips.set_defaults(func=cmd_clips)
```

- [ ] **Step 7: Verify the command is registered**

Run:
```bash
cd rag && python3 cli.py clips --help
```
Expected: usage text showing `workspace_id`, `question`, and `--json`. No traceback.

- [ ] **Step 8: Commit**

```bash
git add rag/retrieval/clips.py rag/tests/test_clips.py rag/cli.py
git commit -m "feat(clips): cli clips command and plain-text renderer

Marks estimated timestamps with ~ rather than hiding that they drift, and
renders errors distinctly from 'nothing answers' so a rate limit never
reads as an empty corpus."
```

---

### Task 8: API endpoint

**Files:**
- Modify: `rag/api.py` (add a request/response model near the other Pydantic models; add the endpoint after the `/chat` handler which ends at line 636)

**Interfaces:**
- Consumes: `find_clips` (Task 6), `_checked_workspace_dir` and `validate_question` (existing in `rag/api.py`), `require_api_key` (`rag/api.py:74`).
- Produces: `POST /clips`.

- [ ] **Step 1: Add the request model**

In `rag/api.py`, alongside the existing request models (near `ChatRequest`), add:

```python
class ClipsRequest(BaseModel):
    workspace_id: str
    question: str
```

- [ ] **Step 2: Add the endpoint**

In `rag/api.py`, immediately after the `/chat` handler (which ends at line 636), add:

```python
@app.post("/clips", dependencies=[Depends(require_api_key)])
def clips(req: ClipsRequest):
    """Return only the clips that ANSWER the question, plus what can be skipped.

    Unlike /chat this returns no prose — the payload is the clip list, so a frontend can
    render timestamps and embed a player without parsing text.
    """
    _checked_workspace_dir(req.workspace_id)

    try:
        question = validate_question(req.question)
    except ValueError as e:
        raise HTTPException(400, str(e))

    from retrieval.clips import find_clips
    return find_clips(question, workspace_id=req.workspace_id)
```

The return value is already a plain JSON-serializable dict (Task 6), so no `response_model` is declared — matching how `/themes` and `/claims` return raw dicts.

- [ ] **Step 3: Verify the app still imports and the route is registered**

Run:
```bash
cd rag && python3 -c "
import api
paths = {r.path for r in api.app.routes}
assert '/clips' in paths, paths
print('/clips registered')
"
```
Expected: `/clips registered`

If this fails with a missing-dependency ImportError, the environment lacks the runtime requirements; run `python3 -m pip install -r ../requirements.txt` first. This step needs the real dependencies because it imports the FastAPI app — that is why it is a manual verification step and not a CI test.

- [ ] **Step 4: Commit**

```bash
git add rag/api.py
git commit -m "feat(api): POST /clips

Returns the clip list as structured JSON rather than prose, so a frontend
can render timestamps and embed a player without parsing text."
```

---

### Task 9: Answer-gate accuracy harness

The gate is the one new component the existing `evals/evaluate.py` does not cover — that harness measures retrieval, which is provider-independent. Without this task the spec's local-mode claim (§3.5) is an assertion instead of a number.

**Files:**
- Create: `rag/evals/dataset_answergate_v1.json`
- Create: `rag/evals/evaluate_gate.py`
- Create: `rag/tests/test_evaluate_gate.py`

**Interfaces:**
- Consumes: `parse_answer_gate_response`, `build_answer_gate_prompt` (Task 3).
- Produces: `score_gate(dataset: list[dict], verdict_by_key: dict) -> dict` returning `{"total": int, "correct": int, "accuracy": float, "confusion": dict, "missing": int}`, and a runnable `python3 evals/evaluate_gate.py <workspace>`.

- [ ] **Step 1: Create the labeled dataset with its documented shape**

Create `rag/evals/dataset_answergate_v1.json`. The entries below are the required *structure* and the first three rows are placeholders in content only — Step 2 replaces them with real labels from a real workspace. Do not ship the placeholder `chunk_id` values.

```json
[
  {
    "question": "does creatine cause water retention?",
    "workspace_id": "REPLACE_ME",
    "chunk_id": "REPLACE_ME_c01",
    "label": "answers",
    "note": "states the mechanism directly"
  },
  {
    "question": "does creatine cause water retention?",
    "workspace_id": "REPLACE_ME",
    "chunk_id": "REPLACE_ME_c02",
    "label": "mentions",
    "note": "talks about creatine dosing, never about retention"
  },
  {
    "question": "does creatine cause water retention?",
    "workspace_id": "REPLACE_ME",
    "chunk_id": "REPLACE_ME_c03",
    "label": "unrelated",
    "note": "about sleep, not creatine"
  }
]
```

- [ ] **Step 2: Populate it with 20 real hand-labeled rows**

Pick a real workspace that has been through `ingest` → `index` → `extract-claims`. List its chunks:

```bash
cd rag && python3 -c "
import json, sys
chunks = json.load(open('data/workspaces/WORKSPACE_ID/chunks.json'))
for c in chunks[:60]:
    print(c['chunk_id'], '|', c['text'][:110].replace(chr(10), ' '))
"
```

Choose 4-6 questions the corpus plausibly covers. For each, read candidate chunks and label ~20 rows total by hand. **Aim for a realistic mix — roughly a third `answers`, a third `mentions`, a third `unrelated`.** A dataset that is mostly `unrelated` makes a lazy model look accurate.

Replace every `REPLACE_ME` with the real `workspace_id` and real `chunk_id` values.

- [ ] **Step 3: Verify the dataset is well-formed and every chunk_id is real**

Run:
```bash
cd rag && python3 -c "
import json
ds = json.load(open('evals/dataset_answergate_v1.json'))
assert len(ds) >= 20, f'only {len(ds)} rows, need >= 20'
assert not any('REPLACE_ME' in str(r.values()) for r in ds), 'placeholders remain'
ws = {r['workspace_id'] for r in ds}
assert len(ws) == 1, f'expected one workspace, got {ws}'
chunk_ids = {c['chunk_id'] for c in json.load(open(f'data/workspaces/{ws.pop()}/chunks.json'))}
bad = [r['chunk_id'] for r in ds if r['chunk_id'] not in chunk_ids]
assert not bad, f'chunk_ids not in the workspace: {bad}'
from collections import Counter
print(len(ds), 'rows,', dict(Counter(r['label'] for r in ds)))
"
```
Expected: 20+ rows and a label distribution with all three labels represented.

- [ ] **Step 4: Write the failing scoring test**

Create `rag/tests/test_evaluate_gate.py`:

```python
"""
Tests for the answer-gate scoring harness — offline, no network.

  python3 -m pytest rag/tests/test_evaluate_gate.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.evaluate_gate import score_gate

DATASET = [
    {"question": "q1", "chunk_id": "c1", "label": "answers"},
    {"question": "q1", "chunk_id": "c2", "label": "mentions"},
    {"question": "q1", "chunk_id": "c3", "label": "unrelated"},
    {"question": "q2", "chunk_id": "c4", "label": "answers"},
]


def test_all_correct_scores_one():
    predicted = {("q1", "c1"): "answers", ("q1", "c2"): "mentions",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["total"] == 4
    assert result["correct"] == 4
    assert result["accuracy"] == 1.0
    assert result["missing"] == 0


def test_partial_correctness():
    predicted = {("q1", "c1"): "answers", ("q1", "c2"): "answers",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "mentions"}
    result = score_gate(DATASET, predicted)
    assert result["correct"] == 2
    assert result["accuracy"] == 0.5


def test_missing_prediction_counts_as_wrong_and_is_reported():
    predicted = {("q1", "c1"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["missing"] == 3
    assert result["correct"] == 1
    assert result["accuracy"] == 0.25


def test_confusion_records_actual_to_predicted():
    predicted = {("q1", "c1"): "mentions", ("q1", "c2"): "mentions",
                 ("q1", "c3"): "unrelated", ("q2", "c4"): "answers"}
    result = score_gate(DATASET, predicted)
    assert result["confusion"][("answers", "mentions")] == 1
    assert result["confusion"][("answers", "answers")] == 1


def test_empty_dataset_does_not_divide_by_zero():
    result = score_gate([], {})
    assert result["total"] == 0
    assert result["accuracy"] == 0.0
```

- [ ] **Step 5: Run to verify it fails**

Run: `python3 -m pytest rag/tests/test_evaluate_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals.evaluate_gate'`

- [ ] **Step 6: Implement the harness**

Create `rag/evals/evaluate_gate.py`:

```python
"""
ANSWER-GATE EVALUATION

evals/evaluate.py measures RETRIEVAL, which is provider-independent — it runs on local
embeddings and a local cross-encoder, so swapping the LLM cannot change its numbers.

The answer gate is different: it is an LLM call, so its quality varies by provider. This
harness measures it against hand labels so "runs fully local on Ollama" can be published
as a number instead of a hope. Run it once per provider and put BOTH numbers in the README.

  python3 evals/evaluate_gate.py <workspace_id>
  LLM_BACKEND=ollama python3 evals/evaluate_gate.py <workspace_id>
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATASET_PATH = Path(__file__).resolve().parent / "dataset_answergate_v1.json"


def score_gate(dataset: list[dict], verdict_by_key: dict) -> dict:
    """Compare predicted verdicts against hand labels.

    `verdict_by_key` maps (question, chunk_id) -> predicted verdict.

    A MISSING prediction counts as wrong and is also reported separately: a model that
    silently omits a chunk is failing, and averaging it away would hide that.
    """
    correct = 0
    missing = 0
    confusion: Counter = Counter()

    for row in dataset:
        key = (row["question"], row["chunk_id"])
        actual = row["label"]
        predicted = verdict_by_key.get(key)
        if predicted is None:
            missing += 1
            confusion[(actual, "MISSING")] += 1
            continue
        confusion[(actual, predicted)] += 1
        if predicted == actual:
            correct += 1

    total = len(dataset)
    return {
        "total": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "confusion": dict(confusion),
        "missing": missing,
    }


def run(workspace_id: str) -> dict:
    """Call the real gate once per question group, then score the verdicts."""
    from retrieval.clips import build_answer_gate_prompt, parse_answer_gate_response
    from core.llm import generate_content

    dataset = json.loads(DATASET_PATH.read_text())
    chunks_path = Path("data/workspaces") / workspace_id / "chunks.json"
    chunk_by_id = {c["chunk_id"]: c for c in json.loads(chunks_path.read_text())}

    by_question: dict[str, list[dict]] = {}
    for row in dataset:
        by_question.setdefault(row["question"], []).append(row)

    verdict_by_key: dict = {}
    for question, rows in by_question.items():
        chunks = [chunk_by_id[r["chunk_id"]] for r in rows]
        raw = generate_content(build_answer_gate_prompt(question, chunks), task="gate")
        verdicts, rejections = parse_answer_gate_response(raw, chunks)
        for v in verdicts:
            verdict_by_key[(question, v["chunk_id"])] = v["verdict"]
        if rejections:
            print(f"  [{question[:40]}...] {len(rejections)} rejected by validation")

    return score_gate(dataset, verdict_by_key)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-scoring":
        # Offline self-check, matching the convention in evals/evaluate.py.
        fake = [{"question": "q", "chunk_id": "c1", "label": "answers"}]
        assert score_gate(fake, {("q", "c1"): "answers"})["accuracy"] == 1.0
        assert score_gate(fake, {})["missing"] == 1
        print("scoring OK")
        sys.exit(0)

    workspace = sys.argv[1] if len(sys.argv) > 1 else "rag_research"
    import os
    result = run(workspace)
    print(f"\nprovider (LLM_BACKEND): {os.environ.get('LLM_BACKEND', 'auto')}")
    print(f"accuracy: {result['correct']}/{result['total']} = {result['accuracy']:.0%}")
    print(f"missing predictions: {result['missing']}")
    print("\nconfusion (actual -> predicted):")
    for (actual, predicted), n in sorted(result["confusion"].items()):
        flag = "" if actual == predicted else "   <-- wrong"
        print(f"  {actual:10s} -> {predicted:10s}  {n}{flag}")
```

- [ ] **Step 7: Run to verify the tests pass**

Run: `python3 -m pytest rag/tests/test_evaluate_gate.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 8: Verify the offline self-check works**

Run: `cd rag && python3 evals/evaluate_gate.py --test-scoring`
Expected: `scoring OK`

- [ ] **Step 9: Commit**

```bash
git add rag/evals/dataset_answergate_v1.json rag/evals/evaluate_gate.py rag/tests/test_evaluate_gate.py
git commit -m "feat(evals): answer-gate accuracy harness

evaluate.py measures retrieval, which is provider-independent. The gate is
an LLM call, so it needs its own measurement before claiming local mode
works. Missing predictions count as wrong and are reported separately."
```

---

### Task 10: Verify local mode end to end and publish both numbers

The spec (§3.5) calls this the most load-bearing section: it carries two of the four surviving differentiators. This task turns "runs fully local" from a claim into a measured number.

**Files:**
- Modify: `README.md` (add a "Fully local" section and an accuracy table)
- Modify: `rag/core/llm.py:10-18` (document the `gate` task in the module docstring)

**Interfaces:**
- Consumes: `evals/evaluate_gate.py` (Task 9), `cli.py clips` (Task 7).
- Produces: documented, reproducible accuracy numbers. No later task consumes these programmatically.

- [ ] **Step 1: Document the new `gate` task name**

`rag/core/llm.py:154` lists the routing tasks as `"extraction", "adjudication", "synthesis", "chat"`. Task 6 introduced `task="gate"`, which works automatically via `_task_backend`'s `{TASK}_BACKEND` lookup but is undocumented.

In `rag/core/llm.py`, update the docstring listing task names to include `gate`, and add this line to the module docstring's task list:

```
  - "gate"    : the clips answer gate. Route it separately (GATE_BACKEND) if you want
                extraction local and the gate on a cloud model, or vice versa.
```

- [ ] **Step 2: Confirm Ollama is running and has the model**

Run:
```bash
curl -s http://localhost:11434/api/tags | python3 -c "
import json,sys
tags = json.load(sys.stdin)
names = [m['name'] for m in tags.get('models', [])]
print('available:', names)
assert any(n.startswith('llama3.2') for n in names), 'run: ollama pull llama3.2'
"
```
Expected: a model list including `llama3.2` (the default at `rag/core/llm.py:42`).

If Ollama is not running: `ollama serve` in another terminal, then `ollama pull llama3.2`.

- [ ] **Step 3: Run the full pipeline with no API key at all**

Use a workspace that already has a scraped `output.json`. Unset the cloud keys for this shell so a silent fallback cannot fake success:

```bash
cd rag
env -u GEMINI_API_KEY -u MISTRAL_API_KEY -u XAI_API_KEY -u GROK_API_KEY \
  LLM_BACKEND=ollama python3 cli.py extract-claims WORKSPACE_ID
```
Expected: claims extracted with no auth error. If it fails with "Ollama not reachable," return to Step 2.

- [ ] **Step 4: Run `clips` fully locally**

```bash
cd rag
env -u GEMINI_API_KEY -u MISTRAL_API_KEY -u XAI_API_KEY -u GROK_API_KEY \
  LLM_BACKEND=ollama python3 cli.py clips WORKSPACE_ID "a question your corpus covers"
```
Expected: rendered clips, or an honest "No clip in this workspace answers…". Record whatever happens — including a failure — for Step 6.

- [ ] **Step 5: Measure gate accuracy on both providers**

```bash
cd rag
LLM_BACKEND=gemini python3 evals/evaluate_gate.py WORKSPACE_ID
LLM_BACKEND=ollama python3 evals/evaluate_gate.py WORKSPACE_ID
```

Write down both accuracy percentages and both `missing` counts.

- [ ] **Step 6: Record both numbers honestly in the README**

Add this section to `README.md`, filling in the real measured values. **Do not round in our favour and do not omit the local number if it is worse** — a published weak number is the reason anyone believes the strong one.

```markdown
## Fully local — no API key, no caps

Every LLM step can run on a local model through Ollama, so no transcript or query
leaves your machine and there is no per-day quota:

```bash
ollama serve && ollama pull llama3.2
LLM_BACKEND=ollama python3 cli.py clips my_research "your question"
```

Retrieval is always local (local embeddings + a local cross-encoder), so it is
unaffected by provider choice. The answer gate is an LLM call, so it is not —
measured against MEASURED_N hand-labeled examples in
`rag/evals/dataset_answergate_v1.json`:

| Provider | Answer-gate accuracy |
|---|---|
| Gemini (`gemini-3.1-flash-lite`) | MEASURED_GEMINI% |
| Ollama (`llama3.2`, fully local) | MEASURED_OLLAMA% |

Reproduce: `LLM_BACKEND=ollama python3 evals/evaluate_gate.py <workspace>`

You can also split routing — keep bulk claim extraction local and send only the
gate to a cloud model — with `EXTRACTION_BACKEND=ollama GATE_BACKEND=gemini`.

### What this does not do

It shows you which sources answer a question and where they conflict. It does not
evaluate whether an argument is any good, and it cannot check claims against
scientific literature — the corpus is only the videos you added.
```

- [ ] **Step 7: Verify the README has no unreplaced placeholders**

Run:
```bash
grep -n "MEASURED_" README.md && echo "FAIL: placeholders remain" || echo "OK"
```
Expected: `OK`

- [ ] **Step 8: Run the whole offline suite one final time**

Run: `python3 -m pytest rag/tests/ -v`
Expected: every test PASSES — `test_jobs.py`, `test_security.py`, `test_clips.py`, `test_evaluate_gate.py`.

- [ ] **Step 9: Commit**

```bash
git add README.md rag/core/llm.py
git commit -m "docs: verified fully-local mode with measured gate accuracy

Published for both Gemini and Ollama against hand labels. Retrieval is
provider-independent; the gate is not, so it gets its own number rather
than an assurance. Also documents the new 'gate' routing task."
```

---

## Self-Review

**Spec coverage (phases 0-2):**

| Spec requirement | Task |
|---|---|
| §4.1 MIT LICENSE | 1 |
| §4.5 CI running pytest | 1 |
| §4.2 docker-compose committed + verified, PO sidecar | 2 |
| §8 new config constants | 3 |
| §3.2 step 2 answer gate, batched, one call | 3, 6 |
| §3.2 verbatim-substring hallucination guard | 3 |
| §3.2 step 3 conflict flag, batched, new prompt | 5, 6 |
| §3.2 only `contradiction` flags in v1 | 5 |
| §3.2 step 4 skip report | 4, 6 |
| §3.2 ranking tie-break toward non-estimated | 6 |
| §3.2 `CLIP_MAX_RETURNED` cap | 3, 6 |
| §3.3 `cli.py clips` subparser | 7 |
| §3.2 `api.py POST /clips` | 8 |
| §3.5 local mode verified end-to-end | 10 |
| §3.5 `dataset_answergate_v1.json`, both numbers published | 9, 10 |
| §5.1 3s lead, `~` marker, estimated tie-break | 4, 6, 7 |
| §6 all eight listed test rows | 3, 4, 5, 6, 9 |
| Global: infra failure ≠ real verdict | 3, 5, 6, 7, 9 |

**Deliberately out of scope**, per the plan header: §3.1 density (phase 3), §3.4 static demo (phase 4), §4.3 committed demo output (phase 4), §4.6 GitHub metadata and §4.7 rename (phase 5). The §6 test row "interval union over overlapping chunks" belongs to density and moves with it.

**Placeholder scan:** The only intentional placeholders are `REPLACE_ME` in Task 9 Step 1 and `MEASURED_*` in Task 10 Step 6. Both exist because their values can only come from a real measurement, both have an explicit replacement step (9.2, 10.6), and both have a verification step that fails if they survive (9.3, 10.7).

**Type consistency check:**
- `parse_answer_gate_response` returns `(verdicts, rejections)` in Tasks 3, 6, and 9 — consistent.
- Verdict dicts use keys `chunk_id` / `verdict` / `span` everywhere. Task 6 maps `span` onto the clip dict under the same name `span`, and Task 7's renderer reads `c["span"]` — consistent. (Note: the spec §3.2 sketch called this field `verbatim`; the plan standardizes on `span` across all tasks. Anyone comparing the two should treat `span` as authoritative.)
- `build_skip_report` returns `video_count` / `total_seconds` / `video_ids` in Tasks 4, 6, 7 — consistent.
- `parse_conflict_response` returns `list[tuple[int, int]]`, 1-based; Task 6 indexes `clips[a - 1]` — consistent.
- `find_clips` returns `clips` / `skipped` / `llm_calls` / `rejections` / `errors` / `question` / `workspace_id` / `provider`; Task 7's renderer reads only those keys; Task 8 returns the dict unchanged — consistent.
- `task="gate"` is introduced in Task 6, used in Task 9, documented in Task 10 — consistent.
- `format_duration` defined in Task 4, used in Task 7 — consistent.

---

## Execution

Task order matters: 3 → 4 → 5 → 6 → 7 → 8 build on each other's functions, and 9 → 10 need 3 and 7. Tasks 1 and 2 depend on nothing and can go first or in parallel.

Tasks 2, 9, and 10 require a real environment (Docker, a scraped workspace, a running Ollama) and cannot be verified in CI. Everything else is offline and fully covered by tests.
