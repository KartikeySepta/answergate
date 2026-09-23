# YouTube AI Workspace

**An open-source, fully-local alternative to NotebookLM for YouTube research.** Turn a pile
of videos into cited, timestamped answers — running entirely on your own machine.

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

Two modules, one shared `.env`:

```
YouTube-ai-workspace/
├── scraper/              # TRANSCRIPTION — extract audio + metadata + transcript
│   ├── youtube.py        #   Main CLI: URL → audio → transcript → JSON
│   ├── api.py            #   FastAPI wrapper for the scraper
│   ├── security.py       #   URL validation
│   ├── requirements.txt  #   yt-dlp, faster-whisper, google-genai, fastapi, uvicorn
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
│   ├── requirements.txt   #   sentence-transformers, qdrant-client, rank-bm25, etc.
│   └── README.md           #   Detailed RAG usage docs
│
├── .env                  # GEMINI_API_KEY (shared by both modules)
├── .gitignore
└── README.md             # ← you are here
```

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
# 1. Clone
git clone git@github.com:KartikeySepta/YouTube-ai-workspace.git
cd YouTube-ai-workspace

# 2. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your_key_here" > .env   # optional — see "Fully local" below

# 3. Start the PO token provider (required for every scrape)
docker compose up -d pot-provider

# 4. Add a video (one command does everything)
cd rag
python3 cli.py add "https://www.youtube.com/watch?v=VIDEO_ID" my_research

# 5. Use it
python3 cli.py talk my_research          # Interactive cited Q&A
python3 cli.py report my_research        # Generate research brief
cat data/workspaces/my_research/report.md
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

## What Makes This Different

- **Every claim is evidence-backed** — hallucinated chunk_ids are discarded
- **Every citation is verified** — grouped `[Source 1, Source 2]` all checked
- **Cross-video synthesis** — surfaces agreement/disagreement across creators
- **Scope-aware** — "same stat for different countries" is flagged, not collapsed
- **Cost-controlled** — claims cached by content_hash; re-runs don't re-call Gemini
- **Rate-limit resilient** — centralized 429 retry with exponential backoff