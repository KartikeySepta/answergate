# Free Hosting Options for YouTube AI Workspace

Standard free-tier hosting services (like Render, Koyeb, or Fly.io) will not work out-of-the-box for this backend because they limit container memory to **256MB–512MB RAM**. When the Python server attempts to load the text embedding model (`BAAI/bge-small-en-v1.5`) or the transcription system, the container will instantly crash with an **Out Of Memory (OOM)** error.

However, you have **four excellent, completely free ways** to host this backend so you can share a live URL and credentials with your frontend developer.

---

## The 4 Best Free Hosting Options

| Option | Ideal For | RAM | Storage | Est. Setup Time |
| :--- | :--- | :--- | :--- | :--- |
| **1. GitHub Codespaces** | Frontend development sandbox | 8GB–16GB | 32GB Persistent | 2 minutes |
| **2. Local Tunneling (Localtunnel/ngrok)** | Fast, zero-config testing from your Mac | Uses your Mac | Uses your Mac | 1 minute |
| **3. Oracle Cloud Free Tier** | 24/7 permanent server hosting | 24GB | 200GB Persistent | 20 minutes |
| **4. Hugging Face Spaces** | Public Docker container sandbox | 16GB | Ephemeral (resets) | 10 minutes |

---

### Option 1: GitHub Codespaces (Highly Recommended for Development)
If you only need a live API link so a developer can build the frontend, GitHub Codespaces is the easiest and most robust solution. GitHub gives you **60 hours of free execution time per month**.

1.  Push your code repository to a private GitHub repository.
2.  On GitHub, click the green **Code** button and select the **Codespaces** tab -> click **Create codespace on main**.
3.  Once the VS Code environment opens in your browser, open the terminal and start the RAG API:
    ```bash
    cd rag
    uvicorn api:app --reload --port 8000
    ```
4.  Expose the API publicly:
    *   In the bottom panel, click the **Ports** tab.
    *   Find Port `8000` (FastAPI).
    *   Right-click the **Visibility** column for Port 8000 and change it from **Private** to **Public**.
5.  Copy the forwarded URL (which will look like `https://xxxx-8000.app.github.dev`).
6.  **Give this URL and your `API_KEY` credentials to your developer.** They can query this public endpoint directly while building the frontend.

---

### Option 2: Local Tunneling (Localtunnel or ngrok)
Instead of uploading your code to the cloud, you can run the FastAPI server on your local machine and use a free tunneling client to expose it to the internet securely.

1.  Run the RAG API on your Mac:
    ```bash
    cd rag
    uvicorn api:app --reload --port 8000
    ```
2.  Expose port 8000 to the web using a free Node utility (no signup required):
    ```bash
    npx localtunnel --port 8000
    ```
3.  Localtunnel will output a public URL like `https://heavy-lions-jump.loca.lt`.
4.  Give this link and your `API_KEY` credential to your developer. The developer will query this link, and requests will securely route straight to the server running on your Mac.

---

### Option 3: Oracle Cloud Always-Free Instance (Best for Permanent Hosting)
Oracle Cloud Infrastructure (OCI) offers the most generous free-tier in the industry. It gives you a full Linux Virtual Machine (VM) running 24/7 completely free, forever.

*   **Specs**: 4 ARM CPUs, **24GB RAM**, and **200GB SSD persistent storage**.
*   **How to setup**:
    1.  Sign up for an [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) account (requires a credit card for identity verification, but you will not be charged).
    2.  Create an instance using the **Ampere VM.Standard.A1.Flex** shape (choose Ubuntu as the OS).
    3.  Open port `8000` and `8001` in the Oracle VCN Security Lists.
    4.  SSH into your instance, clone your repository, and run using Docker or the Systemd service (see the `HOSTING_GUIDE.md` for steps).

---

### Option 4: Hugging Face Spaces (Docker runtime)
Hugging Face offers free hosting for AI apps with up to **16GB of RAM**. 

1.  Create a free account at [Hugging Face](https://huggingface.co/).
2.  Create a new Space:
    *   Set **SDK** to **Docker** (choose the blank template).
    *   Set space visibility to Public.
3.  Push your repository code (including the `Dockerfile` created in the workspace root) to the Hugging Face Space Git repository.
4.  In the Space's settings tab, add your **Repository Secrets** (environment variables):
    *   `GEMINI_API_KEY` = `your_gemini_key`
    *   `API_KEY` = `your_secret_credentials_key`
5.  Hugging Face will automatically build the container and deploy it, exposing the port publicly.
    *   *Note*: The filesystem resets when the Space restarts. To keep vectors permanently, update the RAG config to connect to a free cluster at [Qdrant Cloud](https://qdrant.tech/) instead of using the local disk.
