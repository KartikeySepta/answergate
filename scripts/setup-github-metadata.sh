#!/usr/bin/env bash
# Set the GitHub repo description and topics.
#
# These two fields are the whole of GitHub's discovery surface: the description becomes the
# page's <title> and Google's meta description, and topics power GitHub's topic pages. A repo
# with neither is effectively unlisted — it can only be found by people who already know it
# exists.
#
# Requires the gh CLI:  brew install gh && gh auth login
#
#   ./scripts/setup-github-metadata.sh
#
# Re-runnable. Both fields are freely editable afterwards, so nothing here is one-way.

set -euo pipefail

command -v gh >/dev/null 2>&1 || {
  echo "gh not found. Install it first:  brew install gh && gh auth login" >&2
  exit 1
}

DESCRIPTION="Open-source, fully-local NotebookLM alternative for YouTube. Ask a question across many videos, get the exact timestamped clips that answer it — conflicts flagged, padding skipped. Reads videos NotebookLM can't (no captions needed). Runs on Ollama: no API key, no source limits."

# Ordered most-searched first. GitHub allows 20; these are the terms people actually type.
TOPICS=(
  notebooklm-alternative
  youtube
  rag
  ollama
  local-llm
  self-hosted
  privacy
  llm
  whisper
  transcription
  semantic-search
  video-search
  timestamps
  citations
  hallucination-detection
  gemini
  qdrant
  fastapi
  python
  cli
)

echo "Setting description (${#DESCRIPTION} chars)..."
gh repo edit --description "$DESCRIPTION"

echo "Setting ${#TOPICS[@]} topics..."
gh repo edit $(printf -- '--add-topic %s ' "${TOPICS[@]}")

echo
echo "Done. Verify:"
echo "  gh repo view --json description,repositoryTopics"
echo
echo "Next, the rename. Every link in the README and demo already points at"
echo "the new name, so they stay broken until you run this:"
echo
echo "    gh repo rename answergate"
echo
echo "GitHub keeps redirects from the old URL, so nothing you have already"
echo "shared will break."
echo
echo "Then two things gh cannot do — set them in the web UI:"
echo "  1. Social preview: Settings -> General -> Social preview."
echo "     Upload docs/demo/social-card.png (already rendered, 1280x640)."
echo "     Without it, shares show a generic avatar card and lose most of"
echo "     their click-through."
echo "  2. Pages: Settings -> Pages -> deploy from branch main, folder /docs."
echo "     That publishes the demo the README links to."
