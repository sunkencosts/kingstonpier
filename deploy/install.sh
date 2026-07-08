#!/usr/bin/env bash
# Install the Kingston Pier API as a systemd service on the Pi.
#
# Auto-detects the repo location and the invoking user, stamps them into the
# unit template, installs it, and starts it. Idempotent — re-run after a
# `git pull` to pick up changes (it re-renders and restarts).
#
#   bash deploy/install.sh            # install + enable + start kingstonpier-api
#   bash deploy/install.sh --dry-run  # print the rendered unit, change nothing
#   KP_PORT=8001 bash deploy/install.sh
#
# The Cloudflare Tunnel route (api.kingstonpier.ca -> http://localhost:8000) is
# configured in the dashboard, not here — see deploy/README.md.

set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

KP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KP_USER="${SUDO_USER:-$USER}"
KP_PORT="${KP_PORT:-8000}"
TEMPLATE="$KP_DIR/systemd/kingstonpier-api.service"
UNIT="kingstonpier-api.service"

echo "repo : $KP_DIR"
echo "user : $KP_USER"
echo "port : $KP_PORT"

render() {
  sed -e "s#__KP_USER__#$KP_USER#g" \
      -e "s#__KP_DIR__#$KP_DIR#g" \
      -e "s#__KP_PORT__#$KP_PORT#g" \
      "$TEMPLATE"
}

if [[ "$DRY_RUN" == "1" ]]; then
  echo "--- rendered $UNIT ---"
  render
  exit 0
fi

# Preflight: the venv/uvicorn must exist, or the service will crash-loop.
if [[ ! -x "$KP_DIR/api/.venv/bin/uvicorn" ]]; then
  echo "ERROR: $KP_DIR/api/.venv/bin/uvicorn not found." >&2
  echo "Create it first:" >&2
  echo "  python3 -m venv $KP_DIR/api/.venv" >&2
  echo "  $KP_DIR/api/.venv/bin/pip install -r $KP_DIR/api/requirements.txt" >&2
  exit 1
fi

render | sudo tee "/etc/systemd/system/$UNIT" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$UNIT"
echo "--- status ---"
sudo systemctl --no-pager --full status "$UNIT" | head -8 || true
echo
echo "Verify locally:  curl -s localhost:$KP_PORT/healthz"
echo "Verify public :  curl -s https://api.kingstonpier.ca/healthz"
