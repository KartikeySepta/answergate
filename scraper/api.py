"""
YouTube Transcript API — standalone transcription service.

Run:  uvicorn api:app --reload --port 8001

Security notes:
  • The `output` parameter was removed from the request model. It let a caller
    name any path on disk and have the server write JSON into it. Callers now
    receive the payload in the response and write it themselves.
  • URLs are validated as real YouTube URLs before reaching yt-dlp.
  • Set API_KEY in .env to require an X-API-Key header on /transcribe.
"""

import os
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from security import auth_enabled, check_api_key, validate_youtube_url  # noqa: E402
from youtube import process_video  # noqa: E402

app = FastAPI(title="YouTube Transcript API", version="1.0.0")

# CORS: localhost dev origins by default; override with ALLOWED_ORIGINS in .env.
_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = (
    [o.strip() for o in _origins_env.split(",") if o.strip()]
    if _origins_env
    else ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Gate transcription behind the shared secret in API_KEY (no-op if unset)."""
    if not check_api_key(x_api_key):
        raise HTTPException(401, "Missing or invalid X-API-Key header")


class VideoRequest(BaseModel):
    """
    Request body for a YouTube transcription job.

    Note: there is deliberately no `output` field. Server-side file paths are
    never accepted from callers — the transcript is returned in the response.
    """

    url: str = Field(..., max_length=2048, description="A YouTube video URL")
    engine: Literal["cloud", "local"] = "local"
    model: Literal["base", "small"] = "small"


class TranscribeResponse(BaseModel):
    metadata: dict[str, Any]
    transcript: str


@app.get("/")
def root() -> dict[str, str]:
    """Return basic API information."""
    return {"message": "YouTube Transcript API", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, Any]:
    """Return API health status."""
    return {"status": "ok", "auth_required": auth_enabled()}


@app.post("/transcribe", response_model=TranscribeResponse, dependencies=[Depends(require_api_key)])
def transcribe(video: VideoRequest) -> dict[str, Any]:
    """
    Transcribe a YouTube video and return metadata + transcript.

    Long-running: expect minutes for a full-length video. This is still a
    synchronous endpoint — move it to a background job before exposing it to
    real traffic.
    """
    try:
        url = validate_youtube_url(video.url)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        # output=None → nothing is written to disk by the server
        return process_video(url=url, engine=video.engine, model=video.model, output=None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}")
