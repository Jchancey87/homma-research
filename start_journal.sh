#!/bin/bash
# ============================================================
# Trading Journal — Tmux Startup Script
# Usage: ./start_journal.sh
#
# Creates 3 windows:
#   0: backend  — Flask API (venv activated)
#   1: frontend — Next.js dev server
#   2: scripts  — venv ready for ingestion/enrichment scripts
# ============================================================

SESSION="trading"
PROJECT="/opt/trading-journal"

# If session already exists, just re-attach
tmux has-session -t $SESSION 2>/dev/null
if [ $? -eq 0 ]; then
  echo "Session '$SESSION' already running — reattaching..."
  tmux attach-session -t $SESSION
  exit 0
fi

echo "Starting Trading Journal tmux session..."

# ── Window 0: Backend ────────────────────────────────────────
tmux new-session -d -s $SESSION -n 'backend'
tmux send-keys -t $SESSION:0 \
  "cd $PROJECT/backend && source venv/bin/activate && uvicorn fastapi_app.main:app --port 5000 --host 0.0.0.0 --reload" C-m

# ── Window 1: Frontend ───────────────────────────────────────
tmux new-window -t $SESSION -n 'frontend'
tmux send-keys -t $SESSION:1 \
  "cd $PROJECT/frontend && export NEXT_PUBLIC_API_URL=http://192.168.0.202:5000 && npm run dev -- -H 0.0.0.0" C-m

# ── Window 2: Scripts (venv pre-activated) ───────────────────
tmux new-window -t $SESSION -n 'scripts'
tmux send-keys -t $SESSION:2 \
  "cd $PROJECT && source backend/venv/bin/activate && echo 'venv active — ready to run scripts'" C-m

# ── Window 3: Celery Worker ──────────────────────────────────
tmux new-window -t $SESSION -n 'celery'
tmux send-keys -t $SESSION:3 \
  "cd $PROJECT/backend && source venv/bin/activate && celery -A fastapi_app.celery_app worker --loglevel=info" C-m

# Focus the backend window on attach
tmux select-window -t $SESSION:0

echo "Done! Attaching to session..."
tmux attach-session -t $SESSION
