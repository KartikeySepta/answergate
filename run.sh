#!/bin/bash
# One-click runner: ./run.sh <youtube_url_or_file> [workspace_name]
#
# Examples:
#   ./run.sh "https://www.youtube.com/watch?v=abc123" ai_research   # single video
#   ./run.sh urls.txt ai_research                                    # batch from file

set -e

INPUT="${1:?Usage: ./run.sh <youtube_url or urls_file> [workspace_name]}"
WORKSPACE="${2:-research}"

cd "$(dirname "$0")/rag"

# Auto-detect: if input is an existing file, use batch; otherwise treat as URL
if [ -f "../$INPUT" ] || [ -f "$INPUT" ]; then
    # Resolve the file path
    if [ -f "../$INPUT" ]; then
        FILE="../$INPUT"
    else
        FILE="$INPUT"
    fi
    echo "🚀 Batch processing from: $INPUT → workspace '$WORKSPACE'"
    echo ""
    python3 cli.py batch "$FILE" "$WORKSPACE"
else
    echo "🚀 Processing: $INPUT → workspace '$WORKSPACE'"
    echo ""
    python3 cli.py add "$INPUT" "$WORKSPACE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Ready! Use these commands:"
echo ""
echo "  cd rag"
echo "  python3 cli.py talk $WORKSPACE          # Chat with your research"
echo "  python3 cli.py chat $WORKSPACE 'question here'  # One-shot Q&A"
echo "  cat data/workspaces/$WORKSPACE/report.md        # Read the report"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
