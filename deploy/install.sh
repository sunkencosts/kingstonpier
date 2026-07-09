#!/usr/bin/env bash
# Install the Kingston Pier systemd services on the Pi.
#
# Two units live in systemd/: the read-only API (kingstonpier-api) and the CV
# worker that samples the feeds and writes readings (kingstonpier-cv-worker).
# This installer auto-detects the repo location and invoking user, stamps them
# into the unit template(s), installs, and starts them. Idempotent — re-run
# after a `git pull` to re-render and restart.
#
#   bash deploy/install.sh                 # install API + worker + backup timer
#   bash deploy/install.sh api             # just the API
#   bash deploy/install.sh worker          # just the CV worker
#   bash deploy/install.sh backup          # just the nightly DB backup timer
#   bash deploy/install.sh --dry-run       # print rendered unit(s), change nothing
#   bash deploy/install.sh worker --dry-run
#   KP_PORT=8001 bash deploy/install.sh api
#
# The Cloudflare Tunnel route (api.kingstonpier.ca -> http://localhost:8000) is
# configured in the dashboard, not here — see deploy/README.md.

set -euo pipefail

TARGET="all"
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    api|worker|backup|all) TARGET="$arg" ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

KP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KP_USER="${SUDO_USER:-$USER}"
KP_PORT="${KP_PORT:-8000}"

echo "repo  : $KP_DIR"
echo "user  : $KP_USER"
echo "port  : $KP_PORT"
echo "target: $TARGET"

render() {  # render <template>
  sed -e "s#__KP_USER__#$KP_USER#g" \
      -e "s#__KP_DIR__#$KP_DIR#g" \
      -e "s#__KP_PORT__#$KP_PORT#g" \
      "$1"
}

install_unit() {  # install_unit <unit-name> <template> [enable:1|0]
  local unit="$1" template="$2" enable="${3:-1}"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "--- rendered $unit ---"
    render "$template"
    return 0
  fi
  render "$template" | sudo tee "/etc/systemd/system/$unit" >/dev/null
  sudo systemctl daemon-reload
  if [[ "$enable" == "1" ]]; then
    sudo systemctl enable --now "$unit"
    echo "--- status: $unit ---"
    sudo systemctl --no-pager --full status "$unit" | head -8 || true
  else
    # e.g. the oneshot backup .service — installed but triggered by its .timer.
    echo "installed $unit (not enabled directly; triggered on schedule)"
  fi
}

preflight_api() {
  if [[ ! -x "$KP_DIR/api/.venv/bin/uvicorn" ]]; then
    echo "ERROR: $KP_DIR/api/.venv/bin/uvicorn not found." >&2
    echo "Create it first:" >&2
    echo "  python3 -m venv $KP_DIR/api/.venv" >&2
    echo "  $KP_DIR/api/.venv/bin/pip install -r $KP_DIR/api/requirements.txt" >&2
    exit 1
  fi
}

preflight_worker() {
  if [[ ! -x "$KP_DIR/tracker/.venv/bin/python" ]]; then
    echo "ERROR: $KP_DIR/tracker/.venv/bin/python not found." >&2
    echo "Create it first (CPU/ARM deps, NOT the CUDA pyproject):" >&2
    echo "  python3 -m venv $KP_DIR/tracker/.venv" >&2
    echo "  $KP_DIR/tracker/.venv/bin/pip install -r $KP_DIR/tracker/requirements-pi.txt" >&2
    exit 1
  fi
  if [[ ! -f "$KP_DIR/tracker/counter_model.pt" ]]; then
    echo "ERROR: $KP_DIR/tracker/counter_model.pt not found." >&2
    echo "The trained model is git-ignored — copy it from your dev box, e.g.:" >&2
    echo "  scp tracker/counter_model.pt <pi>:$KP_DIR/tracker/" >&2
    exit 1
  fi
}

preflight_backup() {
  if [[ ! -x "$KP_DIR/deploy/backup_db.sh" ]]; then
    echo "ERROR: $KP_DIR/deploy/backup_db.sh not found or not executable." >&2
    exit 1
  fi
  if ! command -v rclone >/dev/null 2>&1; then
    echo "NOTE: rclone not installed — backups will run and keep LOCAL snapshots," >&2
    echo "      but won't push off-box until rclone + an R2 remote are configured" >&2
    echo "      (see deploy/README.md). Installing the timer anyway." >&2
  fi
}

if [[ "$TARGET" == "api" || "$TARGET" == "all" ]]; then
  [[ "$DRY_RUN" == "1" ]] || preflight_api
  install_unit "kingstonpier-api.service" "$KP_DIR/systemd/kingstonpier-api.service"
fi

if [[ "$TARGET" == "worker" || "$TARGET" == "all" ]]; then
  [[ "$DRY_RUN" == "1" ]] || preflight_worker
  install_unit "kingstonpier-cv-worker.service" "$KP_DIR/systemd/kingstonpier-cv-worker.service"
fi

if [[ "$TARGET" == "backup" || "$TARGET" == "all" ]]; then
  [[ "$DRY_RUN" == "1" ]] || preflight_backup
  install_unit "kingstonpier-backup.service" "$KP_DIR/systemd/kingstonpier-backup.service" 0
  install_unit "kingstonpier-backup.timer"   "$KP_DIR/systemd/kingstonpier-backup.timer"   1
fi

if [[ "$DRY_RUN" != "1" ]]; then
  echo
  echo "Verify API locally:  curl -s localhost:$KP_PORT/healthz"
  echo "Verify API public :  curl -s https://api.kingstonpier.ca/healthz"
  echo "Worker logs       :  journalctl -u kingstonpier-cv-worker -f"
  echo "Backup schedule   :  systemctl list-timers kingstonpier-backup"
  echo "Run a backup now  :  sudo systemctl start kingstonpier-backup.service"
fi
