#!/usr/bin/env bash
# One-command launcher (macOS / Linux). Creates an isolated env on first run.
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then echo "Setting up (first run, ~1 min)…"; python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -r requirements.txt
[ -z "$ANTHROPIC_API_KEY" ] && echo "!! No ANTHROPIC_API_KEY — auto-read off; manual entry still works."
echo ""
echo "  Deal Studio:  open  http://localhost:8000   (Ctrl+C to stop)"
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
