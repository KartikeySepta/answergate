# Backend Hosting and Deployment Guide

Yes, you are using **FastAPI**! Both backend modules (`rag/api.py` and `scraper/api.py`) are FastAPI applications that run locally using the `uvicorn` server engine.

To share credentials with a developer and make these APIs live, you must host them on a cloud server. This guide covers server requirements, credentials management, and step-by-step deployment.

---

## 1. Key Server Requirements

Because the backend handles AI models (local text embeddings and local audio transcribing) and media processing, the server needs specific hardware specs:

*   **Memory (RAM)**: **Minimum 2GB**, Recommended **4GB**. The local embedding model (`BAAI/bge-small-en-v1.5`) and transcription system load matrices into memory. Less than 2GB of RAM will result in Out-Of-Memory (OOM) crashes.
*   **Disk Space**: **Minimum 10GB**. You must use **Persistent Storage** (a persistent disk volume). By default, this application stores vector indices (Qdrant on disk) and workspace JSON files in the `/app/data` directory. If you host on a stateless platform (like standard Heroku or serverless platforms) without a persistent disk, your database will wipe out every time the server restarts.
*   **FFmpeg (System Dependency)**: The scraper relies on the command-line utility `ffmpeg` to extract audio from YouTube streams. The host environment *must* have it installed.

---

## 2. Setting Up Credentials & Security

To secure your hosted endpoints and share access credentials safely with your frontend developer:

1.  **Generate a Shared Secret (API Key)**:
    Open or create the `.env` file on your server and define a secure key:
    ```env
    API_KEY=your_secure_shared_secret
    GEMINI_API_KEY=AIzaSy... (your Google Gemini API Key)
    ```
2.  **How the Frontend Uses It**:
    When `API_KEY` is present in the `.env` file, the FastAPI server protects all mutating endpoints (`POST /add`, `POST /chat`, `DELETE /workspaces`, etc.). Your frontend developer must send this value in the request headers:
    ```http
    X-API-Key: your_secure_shared_secret
    ```
3.  **Prevent Cross-Origin (CORS) Blocks**:
    Once the frontend developer deploys the frontend web app (e.g. to Vercel, Netlify, or a custom domain), update your server's `.env` file to authorize their origin:
    ```env
    ALLOWED_ORIGINS=https://my-frontend-app.vercel.app,http://localhost:3000
    ```

---

## 3. Deploying Using Docker (Recommended)

We have provided a unified [`Dockerfile`](file:///Users/kartikeysepta/founder/YouTube-ai-workspace/Dockerfile) at the root of the project. It automatically installs Python, FFmpeg, all libraries, and routes traffic.

The Docker container decides which API to run using the `SERVICE_TYPE` environment variable:
*   `SERVICE_TYPE=rag`: Launches the RAG API on port `8000`.
*   `SERVICE_TYPE=scraper`: Launches the Scraper API on port `8001`.

---

## 4. Hosting Options

### Option A: Railway (Easiest & Highly Recommended)
Railway is developer-friendly, handles Docker builds automatically, and supports persistent disk attachments.

1.  Sign in to [Railway.app](https://railway.app) and create a new project.
2.  Connect your GitHub repository.
3.  Add **two** Web Services from the same repository (one for RAG, one for Scraper):
    
    *   **Service 1 (Research RAG API)**:
        *   Expose port: `8000`
        *   Add a **Volume** (Persistent Disk): Go to settings -> Volumes -> Add Volume. Mount it to `/app/data`.
        *   Add Environment Variables:
            *   `SERVICE_TYPE` = `rag`
            *   `API_KEY` = `your_secret_key`
            *   `GEMINI_API_KEY` = `your_gemini_key`
            *   `PORT` = `8000`
            
    *   **Service 2 (Standalone Scraper API)**:
        *   Expose port: `8001`
        *   Add Environment Variables:
            *   `SERVICE_TYPE` = `scraper`
            *   `API_KEY` = `your_secret_key`
            *   `PORT` = `8001`
            
4.  Railway will build both services using the root `Dockerfile` and give you two public `https://...` URLs to give to your developer.

---

### Option B: Render
Render is another easy platform offering Docker container hosting with persistent disks.

1.  Sign in to [Render.com](https://render.com) and create a **Web Service**.
2.  Link your GitHub repository.
3.  Configure the settings:
    *   **Runtime**: `Docker`
    *   **Instance Type**: Starter ($7/month or higher — needs at least 2GB RAM).
    *   **Environment Variables**:
        *   `SERVICE_TYPE` = `rag` (Create a second service for `scraper`)
        *   `API_KEY` = `your_secret_key`
        *   `GEMINI_API_KEY` = `your_gemini_key`
    *   **Disk (For RAG Service only)**: Under advanced settings, click "Add Disk". Set the Mount Path to `/app/data` and size to `10GB`.

---

### Option C: Traditional Virtual Private Server (VPS)
If you prefer standard virtual machines (Ubuntu on DigitalOcean, AWS Lightsail, Linode):

1.  **Install dependencies**:
    ```bash
    sudo apt update
    sudo apt install -y python3-pip python3-venv ffmpeg git
    ```
2.  **Clone & Setup**:
    ```bash
    git clone https://github.com/your-username/YouTube-ai-workspace.git /opt/youtube-ai
    cd /opt/youtube-ai
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Create System Services**:
    Configure Systemd to run both APIs in the background. Create `/etc/systemd/system/rag-api.service`:
    ```ini
    [Unit]
    Description=YouTube RAG FastAPI Service
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/opt/youtube-ai
    ExecStart=/opt/youtube-ai/.venv/bin/uvicorn rag.api:app --host 0.0.0.0 --port 8000
    Restart=always
    EnvironmentFile=/opt/youtube-ai/.env

    [Install]
    WantedBy=multi-user.target
    ```
    Repeat similar configurations for `/etc/systemd/system/scraper-api.service` on port `8001`.
4.  **Start Services**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable --now rag-api scraper-api
    ```
5.  **Expose using Nginx & SSL**:
    Set up Nginx as a reverse proxy to route public incoming traffic to ports `8000` and `8001`, and use Certbot (Let's Encrypt) to secure HTTPS.
