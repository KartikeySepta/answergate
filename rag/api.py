"""
Video RAG Tool — FastAPI endpoints .

Run:  uvicorn api:app --reload --port 8000
Docs: http://localhost:8000/docs (auto-generated Swagger UI)

Security notes:
  • Every workspace_id is validated against a whitelist before touching the
    filesystem — see core/security.py. Path traversal is structurally blocked.
  • Every URL is validated as a real YouTube URL before reaching yt-dlp.
  • Set API_KEY in .env to require an X-API-Key header on mutating endpoints.
  • Set ALLOWED_ORIGINS in .env to lock CORS down to your frontend origin.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.jobs import get_store  # noqa: E402
from core.security import (  # noqa: E402
    auth_enabled,
    check_api_key,
    safe_workspace_path,
    validate_history,
    validate_question,
    validate_workspace_id,
    validate_youtube_url,
)

app = FastAPI(
    title="Video RAG API",
    description="Evidence-first multi-video research tool — grounded Q&A with citation verification",
    version="1.0.0",
)

# CORS: default to localhost dev origins only. Override with a comma-separated
# ALLOWED_ORIGINS in .env for production. "*" is never the default.
# Vite increments its port when one is busy (5173 → 5174 → …), so a small range
# is allowed by default; otherwise a second dev server silently fails CORS.
_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if _origins_env:
    ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]
else:
    _dev_ports = [3000, 5173, 5174, 5175]
    ALLOWED_ORIGINS = [
        f"http://{host}:{port}"
        for port in _dev_ports
        for host in ("localhost", "127.0.0.1")
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Gate an endpoint behind the shared secret in API_KEY.

    No-ops when API_KEY is unset so local single-user usage stays frictionless.
    """
    if not check_api_key(x_api_key):
        raise HTTPException(401, "Missing or invalid X-API-Key header")


# ─── VALIDATION HELPERS ───────────────────────────────────────────────────────

def _checked_workspace_dir(workspace_id: str, must_exist: bool = True) -> Path:
    """Validate the id, resolve it safely, and 404 when the workspace is absent."""
    try:
        ws = safe_workspace_path(_workspaces_dir(), workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if must_exist and not ws.exists():
        raise HTTPException(404, f"Workspace '{workspace_id}' not found")
    return ws


def _workspaces_dir() -> str:
    from core.config import WORKSPACES_DIR
    return WORKSPACES_DIR


def _read_json(path: Path, default: Any) -> Any:
    """Read a JSON file with the handle properly closed; return default if absent."""
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ─── REQUEST / RESPONSE MODELS ────────────────────────────────────────────────

class AddVideoRequest(BaseModel):
    url: str = Field(..., max_length=2048, description="A YouTube video URL")
    workspace_id: str = Field(..., min_length=1, max_length=64)
    engine: Literal["cloud", "local"] = "cloud"


class BatchRequest(BaseModel):
    urls: list[str] = Field(..., max_length=50, description="Up to 50 YouTube URLs")
    workspace_id: str = Field(..., min_length=1, max_length=64)
    engine: Literal["cloud", "local"] = "cloud"


class ChatRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[dict] | None = None
    mode: Literal["grounded", "assist"] = "grounded"


class ClipsRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    sources: dict[str, Any]
    citations_valid: bool
    cited_count: int
    mode: str
    verified: bool          # True only in grounded mode with all citations valid
    caveat: str | None = None   # set in assist mode: answer not verified against sources


class AddTextRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=500000, description="Raw text content to ingest")
    workspace_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(default="Pasted Text", max_length=200)
    source_name: str = Field(default="manual_input", max_length=100)


# ─── BACKGROUND PIPELINE ──────────────────────────────────────────────────────

# Ordered step names, surfaced to the client so a UI can render a checklist.
PIPELINE_STEPS = [
    "scrape", "ingest", "index", "extract_claims", "cluster", "synthesize", "report",
]


def _run_add_pipeline(job) -> dict[str, Any]:
    """
    The whole add-a-video pipeline, executed on the job worker thread.

    Reports progress between steps and honours cancellation at each boundary.
    Runs in a single worker thread, so the Qdrant writer lock, the scraper's
    fixed temp filename, and the shared embedding models are never contended.
    """
    from argparse import Namespace
    from cli import (cmd_cluster, cmd_extract_claims, cmd_index, cmd_ingest,
                     cmd_report, cmd_synthesize)

    url = job.params["url"]
    workspace_id = job.params["workspace_id"]
    engine = job.params.get("engine", "cloud")

    scraper = Path(__file__).resolve().parent.parent / "scraper" / "youtube.py"
    if not scraper.exists():
        raise RuntimeError(f"Scraper not found at {scraper}")

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()

    try:
        # 1. Scrape (download + transcribe) — the slow part, minutes for a long video.
        job.start_step("scrape")
        result = subprocess.run(
            ["python3", str(scraper), url, "--engine", engine, "--output", tmp.name],
            capture_output=True, text=True, timeout=SCRAPE_TIMEOUT_SECONDS,
        )
        if result.stdout:
            job.log_line(result.stdout)
        if result.returncode != 0:
            raise RuntimeError(f"Scraping failed: {result.stderr[-800:]}")
        job.finish_step()

        # 2-7. The RAG pipeline. Each cmd_* prints its own progress, which the
        # job's stdout tee captures into job.log automatically.
        ns_ingest = Namespace(raw_path=tmp.name, workspace_id=workspace_id)
        ns = Namespace(workspace_id=workspace_id)

        for name, fn, arg, optional in [
            ("ingest", cmd_ingest, ns_ingest, False),
            ("index", cmd_index, ns, False),
            ("extract_claims", cmd_extract_claims, ns, False),
            ("cluster", cmd_cluster, ns, False),
            ("synthesize", cmd_synthesize, ns, True),   # rate-limit prone, non-critical
            ("report", cmd_report, ns, False),
        ]:
            job.start_step(name)
            try:
                fn(arg)
            except Exception as e:
                if not optional:
                    raise
                job.log_line(f"WARNING: {name} skipped ({e}) — retry later, the rest is intact.")
            job.finish_step()

        ws = Path(_workspaces_dir()) / workspace_id
        return {
            "workspace_id": workspace_id,
            "videos": len(_read_json(ws / "videos.json", [])),
            "chunks": len(_read_json(ws / "chunks.json", [])),
            "claims": len(_read_json(ws / "claims.json", [])),
            "has_report": (ws / "report.md").exists(),
        }
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        # Release the local Qdrant store from THIS (worker) thread. Its SQLite
        # handle cannot be closed from the main thread at exit, and dropping it
        # here also frees the writer lock so a CLI run is not blocked while the
        # server sits idle.
        try:
            from retrieval.vector_store import close_client_for_thread
            close_client_for_thread()
        except Exception:
            pass


# How long a single scrape may take. A 2-hour video needs well over the old 300s.
SCRAPE_TIMEOUT_SECONDS = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "3600"))

get_store().register("add_video", _run_add_pipeline)


# ─── TEXT INGESTION PIPELINE ──────────────────────────────────────────────────

TEXT_PIPELINE_STEPS = ["ingest", "index", "extract_claims", "cluster", "synthesize", "report"]


def _run_add_text_pipeline(job) -> dict[str, Any]:
    """
    Pipeline for raw text ingestion — skips the scrape step entirely.

    Creates a temporary JSON file in the format the ingestion loader expects,
    then runs the standard RAG pipeline from ingest onward.
    """
    from argparse import Namespace
    from cli import (cmd_cluster, cmd_extract_claims, cmd_index, cmd_ingest,
                     cmd_report, cmd_synthesize)

    text = job.params["text"]
    workspace_id = job.params["workspace_id"]
    title = job.params.get("title", "Pasted Text")
    source_name = job.params.get("source_name", "manual_input")

    # Generate a unique video_id from the text content
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    video_id = f"text_{text_hash}"

    # Build the JSON structure the ingestion loader expects
    doc = [{
        "metadata": {
            "video_id": video_id,
            "title": title,
            "channel": source_name,
            "channel_url": "",
            "upload_date": date.today().strftime("%Y%m%d"),
            "duration_seconds": 0,
            "view_count": 0,
            "like_count": 0,
            "tags": [],
            "description": "",
        },
        "transcript": text,
    }]

    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    try:
        json.dump(doc, tmp)
        tmp.close()

        # Run pipeline steps: ingest → index → extract_claims → cluster → synthesize → report
        ns_ingest = Namespace(raw_path=tmp.name, workspace_id=workspace_id)
        ns = Namespace(workspace_id=workspace_id)

        for name, fn, arg, optional in [
            ("ingest", cmd_ingest, ns_ingest, False),
            ("index", cmd_index, ns, False),
            ("extract_claims", cmd_extract_claims, ns, False),
            ("cluster", cmd_cluster, ns, False),
            ("synthesize", cmd_synthesize, ns, True),
            ("report", cmd_report, ns, False),
        ]:
            job.start_step(name)
            try:
                fn(arg)
            except Exception as e:
                if not optional:
                    raise
                job.log_line(f"WARNING: {name} skipped ({e}) — retry later, the rest is intact.")
            job.finish_step()

        ws = Path(_workspaces_dir()) / workspace_id
        return {
            "workspace_id": workspace_id,
            "video_id": video_id,
            "videos": len(_read_json(ws / "videos.json", [])),
            "chunks": len(_read_json(ws / "chunks.json", [])),
            "claims": len(_read_json(ws / "claims.json", [])),
            "has_report": (ws / "report.md").exists(),
        }
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        try:
            from retrieval.vector_store import close_client_for_thread
            close_client_for_thread()
        except Exception:
            pass


get_store().register("add_text", _run_add_text_pipeline)


# ─── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "Video RAG API", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "auth_required": auth_enabled(),
        "queue_depth": get_store().queue_depth(),
    }


@app.get("/workspaces")
def list_workspaces():
    """List all research workspaces."""
    ws_dir = Path(_workspaces_dir())
    if not ws_dir.exists():
        return {"workspaces": []}

    workspaces = []
    for d in sorted(ws_dir.iterdir()):
        if not d.is_dir():
            continue
        workspaces.append({
            "id": d.name,
            "videos": len(_read_json(d / "videos.json", [])),
            "claims": len(_read_json(d / "claims.json", [])),
            "has_report": (d / "report.md").exists(),
        })
    return {"workspaces": workspaces}


@app.get("/workspaces/{workspace_id}")
def workspace_detail(workspace_id: str):
    """Detailed workspace info: videos, claim counts, themes."""
    ws = _checked_workspace_dir(workspace_id)

    videos = _read_json(ws / "videos.json", [])
    claims = _read_json(ws / "claims.json", [])
    themes = _read_json(ws / "cross_source_themes.json", [])

    return {
        "workspace_id": workspace_id,
        "videos": [{"video_id": v["video_id"], "title": v.get("title"), "channel": v.get("channel"),
                    "duration_seconds": v.get("duration_seconds")} for v in videos],
        "claim_count": len(claims),
        "theme_count": len(themes),
        "has_report": (ws / "report.md").exists(),
    }


@app.post("/add", status_code=202, dependencies=[Depends(require_api_key)])
def add_video(req: AddVideoRequest):
    """
    Queue a video for processing and return immediately with a job id.

    The full pipeline takes minutes, which is far longer than a browser or proxy
    will hold a connection open — so nothing is done inline here. Poll
    GET /jobs/{job_id} for status, progress, and live log output.
    """
    try:
        url = validate_youtube_url(req.url)
        workspace_id = validate_workspace_id(req.workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    store = get_store()
    job = store.submit(
        kind="add_video",
        params={"url": url, "workspace_id": workspace_id, "engine": req.engine},
        steps=PIPELINE_STEPS,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "workspace_id": workspace_id,
        "queue_position": store.queue_depth(),
        "poll": f"/jobs/{job.id}",
    }


@app.post("/batch", status_code=202, dependencies=[Depends(require_api_key)])
def add_batch(req: BatchRequest):
    """
    Queue several videos at once. One job per video so the frontend can show
    per-video progress; the worker runs them one after another.
    """
    try:
        workspace_id = validate_workspace_id(req.workspace_id)
        urls = [validate_youtube_url(u) for u in req.urls]
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not urls:
        raise HTTPException(400, "urls must contain at least one URL")

    store = get_store()
    jobs = [
        store.submit(
            kind="add_video",
            params={"url": u, "workspace_id": workspace_id, "engine": req.engine},
            steps=PIPELINE_STEPS,
        )
        for u in urls
    ]
    return {
        "workspace_id": workspace_id,
        "job_ids": [j.id for j in jobs],
        "count": len(jobs),
        "poll": "/jobs",
    }


@app.post("/add-text", status_code=202, dependencies=[Depends(require_api_key)])
def add_text(req: AddTextRequest):
    """
    Queue raw text for ingestion into a workspace. Skips the scrape step entirely.

    Useful for pasting articles, notes, or any text content that isn't from YouTube.
    Poll GET /jobs/{job_id} for status.
    """
    try:
        workspace_id = validate_workspace_id(req.workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    store = get_store()
    job = store.submit(
        kind="add_text",
        params={
            "text": req.text,
            "workspace_id": workspace_id,
            "title": req.title,
            "source_name": req.source_name,
        },
        steps=TEXT_PIPELINE_STEPS,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "workspace_id": workspace_id,
        "queue_position": store.queue_depth(),
        "poll": f"/jobs/{job.id}",
    }


ALLOWED_DOC_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@app.post("/upload-doc", status_code=202, dependencies=[Depends(require_api_key)])
async def upload_doc(
    file: UploadFile = File(...),
    workspace_id: str = Form(...),
    title: str = Form(default=""),
    source_name: str = Form(default=""),
):
    """
    Upload a .txt, .md, or .pdf file for ingestion into a workspace.

    Extracts text content from the file and submits it through the same
    text ingestion pipeline as POST /add-text. Poll GET /jobs/{job_id} for status.
    """
    try:
        workspace_id = validate_workspace_id(workspace_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Validate file extension
    if not file.filename:
        raise HTTPException(400, "Filename is required")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise HTTPException(
            400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_DOC_EXTENSIONS))}"
        )

    # Read file content
    content_bytes = await file.read()
    if len(content_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB")
    if len(content_bytes) == 0:
        raise HTTPException(400, "File is empty")

    # Extract text
    if ext in (".txt", ".md"):
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content_bytes.decode("latin-1")
            except UnicodeDecodeError:
                raise HTTPException(400, "Could not decode file as text (UTF-8 or Latin-1)")
    elif ext == ".pdf":
        # Attempt basic text extraction from PDF
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(400, "Could not extract text from PDF")
        # Strip out binary noise — keep only printable content
        text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")

    if not text or len(text.strip()) < 10:
        raise HTTPException(400, "Extracted text is too short (minimum 10 characters)")
    if len(text) > 500000:
        text = text[:500000]

    # Use filename as title if not provided
    doc_title = title if title else Path(file.filename).stem
    doc_source = source_name if source_name else "file_upload"

    store = get_store()
    job = store.submit(
        kind="add_text",
        params={
            "text": text,
            "workspace_id": workspace_id,
            "title": doc_title,
            "source_name": doc_source,
        },
        steps=TEXT_PIPELINE_STEPS,
    )
    return {
        "job_id": job.id,
        "status": job.status,
        "workspace_id": workspace_id,
        "filename": file.filename,
        "queue_position": store.queue_depth(),
        "poll": f"/jobs/{job.id}",
    }


# ─── JOB ENDPOINTS ─────────────────────────────────────────────────────────────

@app.get("/jobs")
def list_jobs(status: str | None = None, limit: int = 50):
    """List recent jobs, newest first. Optionally filter by status."""
    store = get_store()
    limit = max(1, min(limit, 200))
    return {
        "queue_depth": store.queue_depth(),
        "jobs": [j.to_dict(include_log=False) for j in store.list(status=status, limit=limit)],
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str, full_log: bool = False):
    """
    Status, progress, and log for a single job.

    Poll this after POST /add. `progress` is 0-100, `current_step` names what is
    happening right now, and `log` carries the pipeline's own output.
    """
    job = get_store().get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    d = job.to_dict(include_log=True)
    if full_log:
        d["log"] = job.log
    return d


@app.delete("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def cancel_job(job_id: str):
    """
    Cancel a job. Queued jobs stop immediately; a running job stops at the next
    step boundary (an in-flight LLM call cannot be interrupted).
    """
    store = get_store()
    if store.get(job_id) is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if not store.cancel(job_id):
        raise HTTPException(409, "Job already finished — nothing to cancel")
    return {"status": "cancelling", "job_id": job_id}


@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(req: ChatRequest):
    """Ask a grounded, citation-verified question against a workspace."""
    _checked_workspace_dir(req.workspace_id)

    try:
        question = validate_question(req.question)
        history = validate_history(req.history)
    except ValueError as e:
        raise HTTPException(400, str(e))

    from chat.engine import ask
    result = ask(question, workspace_id=req.workspace_id, recent_history=history, mode=req.mode)

    return ChatResponse(
        answer=result["answer"],
        sources=result["source_map"],
        citations_valid=result["citation_check"]["all_valid"],
        cited_count=result["citation_check"]["cited_count"],
        mode=result["mode"],
        verified=result["verified"],
        caveat=result.get("caveat"),
    )


@app.post("/clips", dependencies=[Depends(require_api_key)])
def clips(req: ClipsRequest):
    """Return only the clips that ANSWER the question, plus what can be skipped.

    Unlike /chat this returns no prose — the payload is the clip list, so a frontend can
    render timestamps and embed a player at each one without parsing text.
    """
    _checked_workspace_dir(req.workspace_id)

    try:
        question = validate_question(req.question)
    except ValueError as e:
        raise HTTPException(400, str(e))

    from retrieval.clips import find_clips
    return find_clips(question, workspace_id=req.workspace_id)


@app.get("/report/{workspace_id}")
def get_report(workspace_id: str):
    """Return the generated research brief as Markdown."""
    ws = _checked_workspace_dir(workspace_id)
    path = ws / "report.md"
    if not path.exists():
        raise HTTPException(404, "Report not generated yet — add videos and run the pipeline first.")
    return {"workspace_id": workspace_id, "markdown": path.read_text(encoding="utf-8")}


@app.get("/themes/{workspace_id}")
def get_themes(workspace_id: str):
    """Return cross-source themes as JSON."""
    ws = _checked_workspace_dir(workspace_id)
    return {"workspace_id": workspace_id, "themes": _read_json(ws / "cross_source_themes.json", [])}


@app.get("/claims/{workspace_id}")
def get_claims(workspace_id: str, limit: int = 200, offset: int = 0):
    """Return validated claims for a workspace (paginated)."""
    ws = _checked_workspace_dir(workspace_id)
    path = ws / "claims.json"
    if not path.exists():
        raise HTTPException(404, "Claims not extracted yet.")

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    claims = _read_json(path, [])

    return {
        "workspace_id": workspace_id,
        "total": len(claims),
        "limit": limit,
        "offset": offset,
        "claims": claims[offset:offset + limit],
    }


@app.get("/messages/{workspace_id}")
def get_messages(workspace_id: str):
    """Return the persisted conversation for a chat (workspace)."""
    ws = _checked_workspace_dir(workspace_id)
    return {"workspace_id": workspace_id, "messages": _read_json(ws / "messages.json", [])}


@app.delete("/workspaces/{workspace_id}", dependencies=[Depends(require_api_key)])
def delete_workspace_endpoint(workspace_id: str):
    """Delete a chat (workspace): its data folder + vectors."""
    import shutil

    ws = _checked_workspace_dir(workspace_id)

    try:
        from retrieval.vector_store import delete_workspace
        removed = delete_workspace(workspace_id)
    except Exception as e:
        # Surface real failures rather than deleting the folder and leaking vectors.
        raise HTTPException(500, f"Vector cleanup failed, workspace not deleted: {e}")

    shutil.rmtree(ws)
    jobs_removed = get_store().remove_for_workspace(workspace_id)
    return {"status": "deleted", "workspace_id": workspace_id, "vectors_removed": removed, "jobs_removed": jobs_removed}
