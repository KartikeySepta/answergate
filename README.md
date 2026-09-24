# answergate

[![CI](https://github.com/KartikeySepta/answergate/actions/workflows/ci.yml/badge.svg)](https://github.com/KartikeySepta/answergate/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Answer-gate accuracy](https://img.shields.io/badge/answer--gate-92%25%20%7C%200%20fabricated-brightgreen)](#fully-local--no-api-key-no-caps)

**An open-source, fully-local alternative to NotebookLM for YouTube research.** Turn a pile
of videos into cited, timestamped answers — running entirely on your own machine.

**[See it running, no install](https://KartikeySepta.github.io/answergate/demo/)** — real
output over two real videos, with every timestamp playable. Including a question the corpus
cannot answer, where it returns nothing rather than the nearest-sounding passage.

```bash
python3 cli.py clips my_research "does creatine cause bloating?"
```

```
2 clip(s) answer: "does creatine cause bloating?"

[1] @JeffNippard — Creatine: Everything You Need To Know
    ~19:30 → ~20:18   https://youtu.be/xY7abc?t=1167
    "water retention is intramuscular, not subcutaneous — you don't look puffier"
    ! CONFLICTS with [2]

[2] @LaylaNorton — The Truth About Creatine
    8:02 → 9:14   https://youtu.be/qM3def?t=479
    "most people do notice some puffiness in the first two weeks"
    ! CONFLICTS with [1]

9 video(s) had no answering clip — 3h 51m you can skip
```

## Why not just use NotebookLM?

|  | NotebookLM | This |
|---|---|---|
| Videos without captions | ✗ can't ingest them | ✓ transcribes the audio itself |
| Videos newer than 24h | ✗ must wait | ✓ works immediately |
| Where your data goes | Google | ✓ your machine (Ollama, no API key) |
| Source limit | 50 free / 100 Plus | ✓ none |
| Query limit | invisible daily + weekly caps | ✓ none |
| Automatable | ✗ web UI only | ✓ CLI + REST API |
It is **not** a better summarizer than NotebookLM, and it will not tell you which source is
right. It reads videos NotebookLM can't, on hardware you own, without limits.

Ordinary retrieval returns chunks that are *topically similar*, which is why a summarizer
can never tell you a video is padding — it has no notion of a chunk failing to answer. An
**answer gate** labels every retrieved chunk `answers` / `mentions` / `unrelated`, and that
last line is only possible because of it.

Two guarantees, enforced mechanically rather than requested in a prompt:

- **A quote must really be in the transcript.** If the model's span isn't a verbatim
  substring of the chunk, the clip is dropped. You never see text a source didn't say.
- **A rate limit never looks like an empty result.** Infrastructure failures are reported
  separately from "nothing here answers you" — conflating those two is how tools lose trust.

`~` marks a timestamp estimated by word position rather than anchored to a real chapter
marker (see `ingestion/chunker.py`), so links seek 3 seconds early on purpose.
Cost is ~2 LLM calls per question.

## Use it from Claude Code, Cursor, or any MCP client

```json
{
  "mcpServers": {
    "answergate": {
      "command": "python3",
      "args": ["/absolute/path/to/rag/mcp_server.py"],
      "env": { "GEMINI_API_KEY": "..." }
    }
  }
}
```

Your agent gets two tools: `search_clips` and `list_workspaces`. Ask it *"what do my
videos say about X"* and it comes back with timestamped quotes — or with nothing, when
nothing in the corpus answers. That refusal is the point: an agent that gets "no source
answers this" will say so, instead of confabulating from the nearest-sounding passage.

Dependency-free — MCP is JSON-RPC over stdio, so there's no SDK to install.

## Fully local — no API key, no caps

Every LLM step can run on a local model through Ollama, so this is genuinely self-hosted:
no transcript and no query leaves your machine, and there is no per-day quota. If the
privacy of what you research matters — medical questions, competitor analysis, anything
under NDA — that is the difference that matters, and it is one a cloud product cannot offer.

```bash
ollama serve && ollama pull llama3.2
LLM_BACKEND=ollama python3 cli.py clips my_research "your question"
```

Retrieval is always local (local embeddings + a local cross-encoder), so provider choice
cannot affect it. The answer gate *is* an LLM call, so it can — measured against 24
hand-labeled examples in `rag/evals/dataset_answergate_v1.json`:

| Provider | Answer-gate accuracy | Fabricated clips |
|---|---|---|
| Gemini (`gemini-3.1-flash-lite`) | **92%** (22/24) | **0** |
| Ollama (`llama3.2`, fully local) | not yet measured | — |

Both Gemini errors sat on the `mentions`/`unrelated` boundary, which never produces a
false clip. All 7 answering chunks were found and nothing was promoted to `answers`
wrongly — including on a control question the corpus cannot answer at all.

Reproduce, or measure a provider yourself:

```bash
LLM_BACKEND=gemini python3 evals/evaluate_gate.py map
LLM_BACKEND=ollama python3 evals/evaluate_gate.py map
```

You can also split routing — keep bulk claim extraction local and send only the gate to a
cloud model — with `EXTRACTION_BACKEND=ollama GATE_BACKEND=gemini`.

## How much of a video is worth watching

```bash
python3 cli.py density my_research     # no question needed
```

Reports claims per minute per video, derived from counted data rather than an LLM's
opinion. **Measured caveat:** the claim-bearing *percentage* saturates — across 7 real
videos from 6 creators it sat at 87-100%, because chunks are ~180 words and nearly every
chunk yields a claim, so it tracks chunk size rather than substance. It ships as a rough
diagnostic and says so in its own output; it is not a way to rank videos.

## Prerequisites

Beyond Python, the scraper needs two external pieces to reliably pull audio from YouTube:

| Requirement | Why | Install |
|---|---|---|
| **Deno** (JS runtime) | Lets yt-dlp's `web` client pass YouTube's JS challenge, instead of silently returning an empty format list | `brew install deno` |
| **Docker + `bgutil-ytdlp-pot-provider`** | Generates a fresh, video-bound PO Token per request. Without this running, downloads intermittently 403 even when format listing succeeds | see below |
| **FFmpeg** | Required by yt-dlp's audio postprocessor | `brew install ffmpeg` |

**Start the PO Token provider** (must be running *every time* you scrape — it's a background service, not a one-time setup). It's in `docker-compose.yml`, so:

```bash
docker compose up -d pot-provider    # just the sidecar
docker compose up -d                 # or the sidecar + both APIs

# verify it's up:
curl http://127.0.0.1:4416/ping
```

The compose service sets `restart: unless-stopped`, so it survives reboots. If you ever see a `403 Forbidden` on download despite formats listing fine, check this first:

```bash
docker ps   # bgutil-provider should be in the list
```

## Quick Start

```bash
# 1. Install
pip install "answergate[full]"        # or: pipx install "answergate[full]"

# ...or from source, if you want to hack on it
git clone git@github.com:KartikeySepta/answergate.git
cd answergate && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[full]"
echo "GEMINI_API_KEY=your_key_here" > .env   # optional — see "Fully local" below

# 3. Start the PO token provider (required for every scrape)
docker compose up -d pot-provider

# 4. Add a video (one command does everything)
answergate add "https://www.youtube.com/watch?v=VIDEO_ID" my_research

# 5. Ask it something
answergate clips my_research "your question"
```

## Add Multiple Videos at Once

```bash
# Create a URL file
cat > urls.txt << EOF
https://www.youtube.com/watch?v=abc123
https://www.youtube.com/watch?v=def456
https://www.youtube.com/watch?v=ghi789
EOF

# Batch process
cd rag
python3 cli.py batch urls.txt my_research
```

## Run as a Web API

```bash
# RAG API (for frontend)
cd rag && uvicorn api:app --reload --port 8000
# Docs: http://localhost:8000/docs

# Scraper API (standalone transcription)
cd scraper && uvicorn api:app --reload --port 8001
```

`POST /add` and `/transcribe` return a `job_id` immediately and run the pipeline
in the background — frontends poll `GET /jobs/{job_id}` for progress. Long
videos take minutes, so this is expected, not a bug.

## What this does not do

- It does **not** evaluate whether an argument is any good. Like `scite.ai` for papers, it
  can show you that sources conflict; it cannot tell you who is right.
- It cannot check claims against scientific literature. The corpus is only the videos you
  added, so its authority is capped by theirs.
- It is **not** a better summarizer than NotebookLM. If your videos have captions and you
  want a smooth overview, use NotebookLM — it's free and needs no setup.
- It is **not** the fastest way to skip filler in one popular video. [SponsorBlock](https://github.com/ajayyy/SponsorBlock)
  is crowdsourced, instant, and free, and its "highlight" feature jumps straight to the
  point. This earns its keep on the long tail — videos with no crowd data and no captions —
  and when the question is yours rather than the crowd's.

## How It Works

```
YouTube URL
     │
     ▼
┌─────────────┐     ┌─────────────────────────────────────────────┐
│   SCRAPER   │     │              RAG ENGINE                      │
│             │     │                                              │
│ yt-dlp      │     │  ingest → chunk → embed → index             │
│ + Gemini/   │────▶│  extract-claims → cluster → synthesize      │
│   Whisper   │     │  ────────────────────────────────────────    │
│             │     │  chat: retrieve → rerank → Gemini → verify  │
│ → output.json     │  report: cited Markdown brief                │
└─────────────┘     └─────────────────────────────────────────────┘
```

## Cookie-Free by Design

This scraper does **not** use browser cookies or a logged-in Google account.
It relies entirely on:

1. A rotating `player_client` list (`android_vr`, `visionos`, `web`) that
   doesn't depend on an authenticated session.
2. Deno as a real JS runtime so the `web` client can pass YouTube's challenge.
3. The `bgutil-ytdlp-pot-provider` sidecar for per-video PO Tokens.

**Trade-off:** age-restricted, private, and members-only videos will fail —
that's an actual permissions check, not a bot check, and no client trick
bypasses it. Normal public videos work end-to-end without touching any
personal account, which avoids the account-lockout risk that comes with
cookie-based scraping at volume.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Requested format is not available` | `web` client only, no JS runtime | Add `android_vr`/`visionos` to `player_client` |
| `HTTP Error 403: Forbidden` on download (formats list fine) | `bgutil-provider` not running | `docker ps` → restart the container if missing |
| macOS Keychain password prompt | `YT_COOKIES_BROWSER` set in `.env` | Remove it — cookies aren't needed for public videos |
| `No supported JavaScript runtime` warning | Deno not installed | `brew install deno` |

## Layout

Two modules, one shared `.env`:

```
answergate/
├── scraper/              # TRANSCRIPTION — extract audio + metadata + transcript
│   ├── youtube.py        #   Main CLI: URL → audio → transcript → JSON
│   ├── api.py            #   FastAPI wrapper for the scraper
│   ├── security.py       #   URL validation
│   ├── test_*.py         #   Component tests (audio, GPU, metadata, pipeline)
│   └── data.json         #   Sample scraped output
│
├── rag/                  # RESEARCH ENGINE — evidence-first multi-video RAG
│   ├── cli.py             #   Main CLI (12 commands: add, batch, ingest, index,
│   │                      #     extract-claims, cluster, synthesize, report,
│   │                      #     chat, talk, status, evaluate)
│   ├── api.py              #   FastAPI endpoints (POST /add, /chat, GET /report, etc.)
│   ├── core/               #   Config, Gemini wrapper (429 retry), data models
│   ├── ingestion/          #   Parse + chunk transcripts
│   ├── retrieval/          #   Embed, vector store, BM25, hybrid fusion, reranker
│   ├── knowledge/          #   Claim extraction, clustering, synthesis, themes
│   ├── chat/               #   Grounded Q&A with citation verification
│   ├── evals/              #   Retrieval evaluation harness + dataset
│   ├── data/                #   Workspaces (generated, gitignored)
│   └── README.md           #   Detailed RAG usage docs
│
├── requirements.txt      # ALL dependencies — one file, installed from the repo root
├── docker-compose.yml    # both APIs + the mandatory PO-token sidecar
├── .env                  # GEMINI_API_KEY (optional — see "Fully local")
├── .gitignore
└── README.md             # ← you are here
```

## Under the hood

- **Every claim is evidence-backed** — hallucinated chunk_ids are discarded
- **Every citation is verified** — grouped `[Source 1, Source 2]` all checked
- **Cross-video synthesis** — surfaces agreement/disagreement across creators
- **Scope-aware** — "same stat for different countries" is flagged, not collapsed
- **Cost-controlled** — claims cached by content_hash; re-runs don't re-call Gemini
- **Rate-limit resilient** — centralized 429 retry with exponential backoff