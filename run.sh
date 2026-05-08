#!/usr/bin/env bash
# Launch MK-Live Q&A Assistant (backend + frontend)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Start Python backend in background
python3 "$REPO_ROOT/backend/main.py" --port 8765 &
BACKEND_PID=$!
echo "[run] Backend started (PID $BACKEND_PID)"

# Wait for backend to be ready
for i in $(seq 1 20); do
  if curl -sf http://localhost:8765/api/status >/dev/null 2>&1; then
    echo "[run] Backend ready"
    break
  fi
  sleep 0.5
done

# Launch Electron
cd "$REPO_ROOT/frontend"
npm start

# When Electron exits, kill backend
kill $BACKEND_PID 2>/dev/null
