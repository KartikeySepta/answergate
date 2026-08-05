# Use a stable official Python slim image
FROM python:3.11-slim

# Install system dependencies:
# - ffmpeg is strictly required by yt-dlp to extract audio
# - build-essential is useful for compiling any native python modules
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy global requirements file first to utilize Docker layer caching
COPY requirements.txt .

# Install dependencies (includes FastAPI, uvicorn, qdrant-client, faster-whisper, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire workspace into the container
COPY . .

# Expose default ports for both APIs:
# 8000 for the RAG API
# 8001 for the Scraper API
EXPOSE 8000
EXPOSE 8001

# Create default persistent directory (must be mounted by your hosting provider)
RUN mkdir -p /app/data

# Environment variable to control which app starts (defaults to rag)
ENV SERVICE_TYPE=rag

# Startup shell script to dispatch to correct API based on environment configuration
CMD if [ "$SERVICE_TYPE" = "scraper" ]; then \
        uvicorn scraper.api:app --host 0.0.0.0 --port 8001; \
    else \
        uvicorn rag.api:app --host 0.0.0.0 --port 8000; \
    fi
