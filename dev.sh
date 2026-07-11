#!/usr/bin/env bash
# Bring up the whole dev stack in one command and see LIVE counts:
#
#   tracker (--watch, samples the 5 feeds -> readings.db)
#        -> API (FastAPI, reads readings.db)  http://localhost:8000
#        -> dashboard (Astro dev, polls the local API)  http://localhost:4321
#
# Open http://localhost:4321. The first tracker pass takes ~10-20s; until it
# lands the dashboard shows "stale", then flips to live with the real total.
# Ctrl+C stops all three.
#
#   ./dev.sh                 # default ports (API 8000, web 4321)
#   KP_API_PORT=8001 ./dev.sh
#
# One-time setup (if a venv/deps are missing, the preflight tells you the exact
# command). This script does NOT install anything — it only launches.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT="${KP_API_PORT:-8000}"

# --- preflight: everything must already be installed -----------------------
fail=0
if [[ ! -x "$ROOT/tracker/.venv/bin/python" ]]; then
  echo "✗ tracker venv missing. Run:  (cd tracker && uv sync)" >&2; fail=1
fi
if [[ ! -f "$ROOT/tracker/counter_model.pt" ]]; then
  echo "✗ tracker/counter_model.pt missing. Train one:  (cd tracker && ./.venv/bin/python train_counter.py)" >&2; fail=1
fi
if [[ ! -x "$ROOT/api/.venv/bin/uvicorn" ]]; then
  echo "✗ api venv missing. Run:  python3 -m venv api/.venv && api/.venv/bin/pip install -r api/requirements.txt" >&2; fail=1
fi
if [[ ! -d "$ROOT/web/node_modules" ]]; then
  echo "✗ web deps missing. Run:  (cd web && npm install)" >&2; fail=1
fi
[[ "$fail" == 0 ]] || { echo "Fix the above, then re-run ./dev.sh" >&2; exit 1; }

# --- point the dashboard at the LOCAL API -----------------------------------
# Use web/.env.development, NOT web/.env: Astro/Vite loads `.env.development`
# only in dev mode (`astro dev`) and IGNORES it during `astro build`, so this
# localhost URL can never leak into a production bundle. (web/.env, by contrast,
# IS read by build — an earlier version wrote it and baked http://localhost into
# a deploy. We migrate any such leftover away below.)
ENVFILE="$ROOT/web/.env.development"
DESIRED="PUBLIC_API_BASE=http://localhost:$API_PORT"

# One-time migration: a stale dev-written web/.env poisons `npm run build`.
if [[ -f "$ROOT/web/.env" ]] && grep -qiE '^PUBLIC_API_BASE=https?://localhost:' "$ROOT/web/.env"; then
  rm -f "$ROOT/web/.env"
  echo "[dev] removed stale web/.env (dev URL now lives in .env.development, which build ignores)"
fi

if [[ ! -f "$ENVFILE" ]]; then
  echo "$DESIRED" > "$ENVFILE"
  echo "[dev] wrote web/.env.development -> $DESIRED"
elif grep -qiE '^PUBLIC_API_BASE=https?://localhost:' "$ENVFILE"; then
  if ! grep -qxF "$DESIRED" "$ENVFILE"; then
    sed -i -E "s#^PUBLIC_API_BASE=https?://localhost:[0-9]+.*#$DESIRED#" "$ENVFILE"
    echo "[dev] updated web/.env.development -> $DESIRED"
  fi
else
  echo "[dev] ⚠  web/.env.development sets a non-localhost PUBLIC_API_BASE — the dashboard"
  echo "[dev]    will poll that (possibly prod), not your local tracker. Set it to:"
  echo "[dev]    $DESIRED"
fi

# --- launch all three, prefixing their logs; Ctrl+C stops everything -------
pids=()
cleanup() {
  trap - INT TERM EXIT
  echo; echo "[dev] stopping..."
  for p in "${pids[@]}"; do
    pkill -TERM -P "$p" 2>/dev/null || true   # children (e.g. Vite's esbuild)
    kill -TERM "$p" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "[dev] starting tracker + API (:$API_PORT) + dashboard (:4321)"
( cd "$ROOT/tracker" && exec ./.venv/bin/python -u crowd_tracker.py --watch 3 ) \
    > >(sed -u 's/^/[tracker] /') 2>&1 & pids+=($!)
( cd "$ROOT/api" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" --reload --reload-dir app ) \
    > >(sed -u 's/^/[api]     /') 2>&1 & pids+=($!)
# Exec astro directly (not `npm run dev`) so the recorded PID is the server and
# Ctrl+C actually stops it — npm doesn't forward the signal to its child.
( cd "$ROOT/web" && exec ./node_modules/.bin/astro dev ) \
    > >(sed -u 's/^/[web]     /') 2>&1 & pids+=($!)

echo "[dev] ─────────────────────────────────────────────"
echo "[dev]  Dashboard:  http://localhost:4321"
echo "[dev]  API:        http://localhost:$API_PORT/now"
echo "[dev]  Ctrl+C to stop all three."
echo "[dev] ─────────────────────────────────────────────"
wait
