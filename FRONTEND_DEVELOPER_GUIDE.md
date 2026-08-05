# YouTube AI Workspace — Frontend Developer Guide & API Spec

This document is a complete handoff specification for building a web-based frontend client for the **YouTube AI Workspace**. 

The backend consists of two service modules that run as separate FastAPI servers. They share a single `.env` configuration file but expose distinct APIs.

---

## 1. System Architecture Overview

The system is split into two service instances:
1. **RAG API (Port 8000)**: The main Research Engine. It handles multi-video workspaces, evidence-first claim extraction, synthesis, reporting, and grounded chat.
2. **Scraper API (Port 8001)**: A standalone transcription and metadata extraction engine.

### High-Level Data Flow

```
                     YouTube Video URL
                            │
                            ▼
 ┌─────────────────────────────────────────────────────┐
 │                 1. SCRAPER ENGINE                   │
 │ Downloads audio, extracts metadata, runs Whisper /  │
 │ Gemini Flash, returns transcript + clean metadata.  │
 └──────────────────────────┬──────────────────────────┘
                            │ (Transcript + Metadata)
                            ▼
 ┌─────────────────────────────────────────────────────┐
 │                   2. RAG PIPELINE                   │
 │  • Ingest & Chunk: Splits transcript into overlap   │
 │    segments, dedups by content hash.                │
 │  • Index: Embeds and indexes chunks (Qdrant).       │
 │  • Extract Claims: Extracts atomic claims, verified │
 │    against source chunks to block LLM hallucinations.│
 │  • Cluster & Synthesize: Group claims, analyze      │
 │    cross-source themes (agreement/conflict/etc.).   │
 │  • Report: Generates a cited Markdown brief.        │
 │  • Chat: Interactive grounded Q&A with real-time   │
 │    citation verification check.                     │
 └─────────────────────────────────────────────────────┘
```

---

## 2. Setup & Execution Guide

### Spinning Up the Servers
To run the project locally, install dependencies and start both servers:

```bash
# Setup virtual environment and dependencies (if not done)
python3 -m venv .venv
source .venv/bin/activate
pip install -r scraper/requirements.txt
pip install -r rag/requirements.txt

# Start RAG API (Port 8000)
cd rag
uvicorn api:app --reload --port 8000

# Start Scraper API (Port 8001)
cd ../scraper
uvicorn api:app --reload --port 8001
```

### Security & CORS Configuration
Both services configure CORS based on the `.env` file at the project root:

*   **CORS Origins**: By default, the APIs allow `localhost` dev origins (`3000`, `5173`, `5174`, `5175`). If your frontend runs on a custom port, set it in your `.env` file:
    ```env
    ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173,http://your-custom-origin.com
    ```
*   **Authentication**: If `API_KEY` is set in the `.env` file, all mutating endpoints (`POST`, `DELETE`, `PUT`) will require an `X-API-Key` HTTP header. Keep this header optional in local development but present in the configuration.
    ```env
    API_KEY=your_secure_shared_secret
    ```
    ```http
    X-API-Key: your_secure_shared_secret
    ```

---

## 3. UI/UX Pages & Flow Specification

A premium frontend should be built around a modern, responsive layout (ideally a left-sidebar navigation and multi-column details view).

### A. Workspaces Dashboard (Home Screen)
*   **Purpose**: List all existing research workspaces, create new ones, and delete unwanted ones.
*   **Data Source**: `GET /workspaces`
*   **UI Components**:
    *   A grid of cards representing each workspace.
    *   Each card displays:
        *   **Workspace ID** (name).
        *   **Video Count** (number of ingested videos).
        *   **Claim Count** (number of extracted, evidence-backed statements).
        *   **Report Status**: A badge showing if a cited Markdown brief has been compiled yet.
    *   "New Workspace" button: prompts for a unique, filesystem-safe alphanumeric string (e.g., `ai_agents_research`).
    *   "Delete Workspace" button: deletes the directory and drops vector records. Includes a confirmation modal.

### B. Workspace Detail & Pipeline Status
*   **Purpose**: Monitor video processing and configure research inputs.
*   **UI Components**:
    *   **Add Video Form**: Input for a YouTube video URL, dropdown for processing engine (`cloud` or `local`), and a submit button.
    *   **Batch Ingest Form**: TextArea for pasting multiple YouTube URLs (one per line) to process them in sequence.
    *   **Active Job Tracker**: When a video is submitted, the API returns a `job_id`. The client must show a processing dialog or panel that polls `GET /jobs/{job_id}` and renders a visual progress checklist of the 7-step pipeline:
        1.  `scrape` (Downloading audio + transcribing — *slowest step*)
        2.  `ingest` (Parsing, chunking, and deduplicating transcripts)
        3.  `index` (Generating embeddings and saving to Qdrant vector store)
        4.  `extract_claims` (Extracting facts & checking evidence)
        5.  `cluster` (Merging identical claims and resolving overlapping stances)
        6.  `synthesize` (Calculating stats, consensus, and cross-source themes)
        7.  `report` (Compiling the final cited markdown document)
    *   **Job Logger**: A collapsible terminal console displaying the live stdout log (`job.log` from the job status payload) for debugging errors.

### C. Workspace View (Multi-Tab Interface)
Once a workspace is selected, show a 3-tab panel:

#### Tab 1: Research Brief (Report)
*   **API**: `GET /report/{workspace_id}`
*   **UI**:
    *   Render the markdown response using a Markdown parser (like `react-markdown` or similar). Include styling for tables, headers, and code blocks.
    *   **Interactive Citations**: The Markdown contains citations formatted as `[Source 1]`, `[Source 2]`, etc. You must intercept these inline bracket elements to make them interactive (see Section 5 for implementation recipes). Clicking a citation should highlight/open the source details in a side panel.

#### Tab 2: Grounded Q&A Chat
*   **API**: `POST /chat`
*   **UI**:
    *   A chat interface mimicking a modern LLM chat assistant.
    *   **Toggle Switch**: `Grounded Mode` (default) vs `Assist Mode`.
        *   *Grounded Mode*: High precision, strictly verified claims only. Refuses to answer if the transcript doesn't cover the query.
        *   *Assist Mode*: Allows the LLM to blend transcript data with its own general training knowledge to help write scripts, code, or execute complex brainstorming (shows a yellow caution badge notifying the user that general LLM details are included).
    *   **Chat History**: Maintain a message array of `{role: "user" | "assistant", content: string}` and pass it into the request body as `history` for multi-turn chats.
    *   **Citation Side-Panel / Cards**: Under every assistant response, render cards for the sources used. Match the `[Source N]` tags inside the response to the `sources` map returned in the JSON payload:
        *   Show the video thumbnail, title, channel name, and timestamp range.
        *   **Deep Linking**: Make the timestamp linkable. When clicked, it should open the YouTube video in a new tab or embed an iframe player pointing directly to the exact second (e.g. `https://youtu.be/VIDEO_ID?t=123`).
        *   **Verification Badge**: If the response has `verified: true`, show a green check icon stating *"All Citations Verified Against Raw Transcripts"*. If `citations_valid` is false, show a red warning indicator highlighting invalid/hallucinated source IDs.

#### Tab 3: Claims & Synthesis Explorer
*   **API**: `GET /claims/{workspace_id}` and `GET /themes/{workspace_id}`
*   **UI**:
    *   A list of extracted claims, searchable by keyword or topic. Show stance badges (e.g., Green for `support`, Grey for `neutral`, Red for `contradict`).
    *   **Themes section**: Displays how different videos connect. For instance, show cards showing agreement or conflict between video uploads. Example:
        *   *Theme ID*: `theme_0001` (Relationship: `agreement`)
        *   *Note*: "Both creator X and creator Y agree that MCP is a game-changer for AI agents."
        *   Displays the underlying claims that support this theme side-by-side.

---

## 4. API Endpoints Reference

### RAG Service (Port 8000)

#### 1. API Health Check
*   **Method**: `GET`
*   **Path**: `/health`
*   **Response**: `200 OK`
    ```json
    {
      "status": "ok",
      "auth_required": false,
      "queue_depth": 0
    }
    ```

#### 2. List Workspaces
*   **Method**: `GET`
*   **Path**: `/workspaces`
*   **Response**: `200 OK`
    ```json
    {
      "workspaces": [
        {
          "id": "my_topic",
          "videos": 3,
          "claims": 42,
          "has_report": true
        }
      ]
    }
    ```

#### 3. Workspace Details
*   **Method**: `GET`
*   **Path**: `/workspaces/{workspace_id}`
*   **Response**: `200 OK`
    ```json
    {
      "workspace_id": "my_topic",
      "videos": [
        {
          "video_id": "_d0duu3dED4",
          "title": "Why Everyone’s Talking About MCP?",
          "channel": "ByteByteGo",
          "duration_seconds": 303
        }
      ],
      "claim_count": 42,
      "theme_count": 4,
      "has_report": true
    }
    ```

#### 4. Add Video to Workspace (Start Ingest Job)
*   **Method**: `POST`
*   **Path**: `/add`
*   **Headers**: `X-API-Key` (conditional)
*   **Request Body**:
    ```json
    {
      "url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "workspace_id": "my_topic",
      "engine": "cloud"
    }
    ```
    *Note: `engine` can be `"cloud"` (using Gemini API for transcription) or `"local"` (using Faster-Whisper).*
*   **Response**: `202 Accepted`
    ```json
    {
      "job_id": "job_1700000000_abc123",
      "status": "queued",
      "workspace_id": "my_topic",
      "queue_position": 1,
      "poll": "/jobs/job_1700000000_abc123"
    }
    ```

#### 5. Add Batch of Videos
*   **Method**: `POST`
*   **Path**: `/batch`
*   **Headers**: `X-API-Key` (conditional)
*   **Request Body**:
    ```json
    {
      "urls": [
        "https://www.youtube.com/watch?v=123",
        "https://www.youtube.com/watch?v=456"
      ],
      "workspace_id": "my_topic",
      "engine": "cloud"
    }
    ```
*   **Response**: `202 Accepted`
    ```json
    {
      "workspace_id": "my_topic",
      "job_ids": ["job_abc", "job_def"],
      "count": 2,
      "poll": "/jobs"
    }
    ```

#### 6. Poll Ingestion Job Status
*   **Method**: `GET`
*   **Path**: `/jobs/{job_id}`
*   **Query Parameters**: `full_log=false` (Set true to fetch the entire stdout pipeline log, otherwise returns trailing 60 lines).
*   **Response**: `200 OK`
    ```json
    {
      "job_id": "job_1700000000_abc123",
      "kind": "add_video",
      "params": {
        "url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "workspace_id": "my_topic",
        "engine": "cloud"
      },
      "status": "running",
      "steps": ["scrape", "ingest", "index", "extract_claims", "cluster", "synthesize", "report"],
      "step_index": 2,
      "current_step": "index",
      "progress": 28,
      "created_at": 1700000000.0,
      "started_at": 1700000001.0,
      "finished_at": null,
      "duration_seconds": 15.4,
      "error": null,
      "result": null,
      "log": "[scrape] Audio download complete.\n[ingest] Generated 12 chunks...\n"
    }
    ```
    *Job statuses returned can be: `"queued"`, `"running"`, `"done"`, `"failed"`, `"cancelled"`, or `"interrupted"`.*

#### 7. Cancel Active Job
*   **Method**: `DELETE`
*   **Path**: `/jobs/{job_id}`
*   **Headers**: `X-API-Key` (conditional)
*   **Response**: `200 OK`
    ```json
    {
      "status": "cancelling",
      "job_id": "job_1700000000_abc123"
    }
    ```

#### 8. Grounded Chat
*   **Method**: `POST`
*   **Path**: `/chat`
*   **Headers**: `X-API-Key` (conditional)
*   **Request Body**:
    ```json
    {
      "workspace_id": "my_topic",
      "question": "What is the primary benefit of MCP?",
      "history": [
        {"role": "user", "content": "Tell me about MCP."},
        {"role": "assistant", "content": "MCP stands for Model Context Protocol [Source 1]."}
      ],
      "mode": "grounded"
    }
    ```
    *Note: `mode` can be `"grounded"` or `"assist"`.*
*   **Response**: `200 OK`
    ```json
    {
      "answer": "The primary benefit of MCP is that it allows AI models to autonomously select tools [Source 1], avoiding hard-coded logic.",
      "sources": {
        "Source 1": {
          "chunk_id": "vid123_c0001",
          "video_id": "vid123",
          "video_title": "Why Everyone’s Talking About MCP?",
          "channel": "ByteByteGo",
          "timestamp": "~0:04–~0:45",
          "is_estimated": true
        }
      },
      "citations_valid": true,
      "cited_count": 1,
      "mode": "grounded",
      "verified": true,
      "caveat": null
    }
    ```

#### 9. Get Research Report
*   **Method**: `GET`
*   **Path**: `/report/{workspace_id}`
*   **Response**: `200 OK`
    ```json
    {
      "workspace_id": "my_topic",
      "markdown": "# Research Brief: MCP\n\n## Core Findings\n* MCP allows dynamic tools [Source 1].\n..."
    }
    ```

#### 10. Get Synthesized Cross-Video Themes
*   **Method**: `GET`
*   **Path**: `/themes/{workspace_id}`
*   **Response**: `200 OK`
    ```json
    {
      "workspace_id": "my_topic",
      "themes": [
        {
          "theme_id": "theme_0000",
          "member_claim_ids": ["claim_a1", "claim_b2"],
          "videos": ["vidA", "vidB"],
          "cosine": 0.836,
          "relationship": "different_context",
          "synthesis_note": "Video A focuses on technical setup, whereas Video B focuses on business values."
        }
      ]
    }
    ```

#### 11. Get Extracted Claims
*   **Method**: `GET`
*   **Path**: `/claims/{workspace_id}`
*   **Query Parameters**: `limit=200`, `offset=0`
*   **Response**: `200 OK`
    ```json
    {
      "workspace_id": "my_topic",
      "total": 42,
      "limit": 200,
      "offset": 0,
      "claims": [
        {
          "claim_id": "_d0duu3dED4_c0001_claim0",
          "video_id": "_d0duu3dED4",
          "claim": "MCP allows AI models to autonomously select tools based on conversation rather than following hard-coded logic.",
          "claim_type": "fact",
          "stance": "support",
          "evidence": [
            {
              "chunk_id": "_d0duu3dED4_c0001",
              "evidence_text": "Claude can autonomously select the tool based on conversation."
            }
          ],
          "topics": ["MCP", "AI autonomy"],
          "cluster_id": "cluster_0001"
        }
      ]
    }
    ```

#### 12. Delete Workspace
*   **Method**: `DELETE`
*   **Path**: `/workspaces/{workspace_id}`
*   **Headers**: `X-API-Key` (conditional)
*   **Response**: `200 OK`
    ```json
    {
      "status": "deleted",
      "workspace_id": "my_topic",
      "vectors_removed": true
    }
    ```

---

### Scraper Service (Port 8001)

#### 1. Standalone Direct Transcription
*   **Method**: `POST`
*   **Path**: `/transcribe`
*   **Headers**: `X-API-Key` (conditional)
*   **Request Body**:
    ```json
    {
      "url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "engine": "local",
      "model": "small"
    }
    ```
    *Note: `engine` can be `"local"` or `"cloud"`. `model` defaults to `"small"` (or `"base"`).*
*   **Response**: `200 OK` (Note: Takes minutes to return since it runs synchronously).
    ```json
    {
      "metadata": {
        "video_id": "VIDEO_ID",
        "title": "Video Title",
        "channel": "Channel Name",
        "channel_url": "https://youtube.com/@...",
        "subscriber_count": 1200000,
        "duration_seconds": 303,
        "view_count": 460000,
        "like_count": 11000,
        "comment_count": 500,
        "upload_date": "20250402",
        "tags": ["AI", "Tech"],
        "categories": ["Tech"],
        "thumbnail_url": "https://i.ytimg.com/vi/...",
        "is_live": false,
        "language": "en",
        "description": "Video description text..."
      },
      "transcript": "[00:00] First segment text\n[00:04] Second segment text..."
    }
    ```

---

## 5. UI Implementation Helper Snippets

### Ingestion Polling Hook (React + TypeScript)
Use this hook pattern to submit a video and track its progress through the 7-step pipeline.

```typescript
import { useState, useEffect } from 'react';

type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrupted';

interface JobResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  current_step: string;
  steps: string[];
  error: string | null;
  log?: string;
}

export function usePipelineJob(jobId: string | null, onComplete?: () => void) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    setLoading(true);
    let intervalId: NodeJS.Timeout;

    const pollJob = async () => {
      try {
        const response = await fetch(`http://localhost:8000/jobs/${jobId}?full_log=false`);
        if (!response.ok) throw new Error("Failed to fetch job details");
        
        const data: JobResponse = await response.json();
        setJob(data);

        if (data.status === 'done') {
          setLoading(false);
          clearInterval(intervalId);
          if (onComplete) onComplete();
        } else if (['failed', 'cancelled', 'interrupted'].includes(data.status)) {
          setLoading(false);
          clearInterval(intervalId);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    // Run first poll immediately, then every 3 seconds
    pollJob();
    intervalId = setInterval(pollJob, 3000);

    return () => clearInterval(intervalId);
  }, [jobId]);

  return { job, loading };
}
```

### Parsing YouTube Timestamps
Converting string representations of timestamps into seconds allows you to trigger inline players or link straight to the source material.

```typescript
/**
 * Converts a timestamp range string into an integer starting second.
 * Handles estimated prefixes '~' and formats like '2:03' or '1:02:04'.
 * Input: "~2:03–~2:45" -> Output: 123
 */
export function getStartSeconds(timestampStr: string): number {
  // Strip estimation symbol '~' and take only the start timestamp before the dash '–' (or '-')
  const cleanStr = timestampStr.replace(/~/g, '').split(/[–-]/)[0].trim();
  const parts = cleanStr.split(':').map(Number);
  
  if (parts.length === 3) {
    // HH:MM:SS
    const [h, m, s] = parts;
    return h * 3600 + m * 60 + s;
  } else if (parts.length === 2) {
    // MM:SS
    const [m, s] = parts;
    return m * 60 + s;
  }
  return 0;
}

/**
 * Returns a deep-linked YouTube URL.
 * Input: "EP9zPS1jNwA", "~2:03–~2:45"
 * Output: "https://www.youtube.com/watch?v=EP9zPS1jNwA&t=123s"
 */
export function getYouTubeUrlWithTime(videoId: string, timestampStr: string): string {
  const seconds = getStartSeconds(timestampStr);
  return `https://www.youtube.com/watch?v=${videoId}&t=${seconds}s`;
}
```

### Handling Citation Click Interceptions
To make the text `[Source 1]` clickable in React:

```typescript
import React from 'react';

interface CitationsRendererProps {
  text: string;
  sources: Record<string, any>;
  onCitationClick: (sourceLabel: string, sourceData: any) => void;
}

export const GroundedResponse: React.FC<CitationsRendererProps> = ({ text, sources, onCitationClick }) => {
  // Regex matches [Source X] where X is a digit
  const parts = text.split(/(\[Source \d+\])/g);

  return (
    <div className="prose text-white">
      {parts.map((part, index) => {
        const isCitation = part.startsWith('[Source ') && part.endsWith(']');
        if (isCitation) {
          const label = part.slice(1, -1); // "Source 1"
          const sourceData = sources[label];
          
          if (!sourceData) return <span key={index}>{part}</span>;
          
          return (
            <button
              key={index}
              onClick={() => onCitationClick(label, sourceData)}
              className="inline-flex items-center mx-0.5 px-1.5 py-0.5 rounded text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white border-none cursor-pointer transition-colors"
              title={`${sourceData.video_title} (${sourceData.timestamp})`}
            >
              {label}
            </button>
          );
        }
        return <span key={index}>{part}</span>;
      })}
    </div>
  );
};
```

---

## 6. CSS / Theme System Guideline
To keep the visual presentation sleek, the frontend should follow a unified dark-mode-first styling palette.

*   **Colors**:
    *   *Background*: Deep Dark Grey / Charcoal (`#0f0f12`, `#16161a`)
    *   *Cards*: Semi-transparent Slate (`rgba(30, 30, 38, 0.6)`) with `backdrop-filter: blur(10px)` (Glassmorphism).
    *   *Accent Primary*: Electric Blue (`#3b82f6`) or Neon Purple (`#a855f7`) for interactive highlights.
    *   *Green (Verified Status)*: Emerald (`#10b981`)
    *   *Yellow (Assist caveat / estimates)*: Amber (`#f59e0b`)
*   **Typography**: Clean sans-serif fonts such as *Inter*, *Outfit*, or *Roboto*.
*   **Micro-animations**: Use subtle scales (`scale(1.02)`) and transitions (`transition: all 0.2s ease-in-out`) on workspace cards, list tabs, and buttons to give the UI a responsive, fluid feel.
