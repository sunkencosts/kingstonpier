#!/usr/bin/env bash
# Back up the readings DB safely and push it OFF the SD card to Cloudflare R2.
#
# Runs on the Pi (usually from the kingstonpier-backup.timer). Steps:
#   1. Online snapshot via SQLite's backup API — consistent even while the
#      worker is mid-write (no locking, no stopping the service).
#   2. gzip it.
#   3. Rotate a small LOCAL cache (fast restore) — keep the last N.
#   4. Upload to R2 with rclone (the durable, off-box copy).
#
# The SD card is the thing we're insuring against, so the local cache is just a
# convenience — R2 is the real backup.
#
#   bash deploy/backup_db.sh            # snapshot + rotate + upload
#   bash deploy/backup_db.sh --local    # snapshot + rotate only (skip R2)
#
# Config (env, e.g. from the systemd unit):
#   KP_DB_PATH      DB to back up            (default: <repo>/db/data/readings.db)
#   KP_BACKUP_DIR   local cache dir          (default: $HOME/kingstonpier-backups)
#   KP_BACKUP_KEEP  local snapshots to keep  (default: 14)
#   KP_R2_REMOTE    rclone dest, e.g. r2:kingstonpier-backups   (required for upload)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${KP_DB_PATH:-$REPO_DIR/db/data/readings.db}"
BACKUP_DIR="${KP_BACKUP_DIR:-$HOME/kingstonpier-backups}"
KEEP="${KP_BACKUP_KEEP:-14}"
R2_REMOTE="${KP_R2_REMOTE:-}"
UPLOAD=1
[[ "${1:-}" == "--local" ]] && UPLOAD=0

if [[ ! -f "$DB" ]]; then
  echo "No DB at $DB yet — nothing to back up (worker hasn't written)." >&2
  exit 0
fi

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
snap="$BACKUP_DIR/readings-$stamp.db"
gz="$snap.gz"

# 1. Consistent online snapshot (reads the source read-only; safe mid-write).
python3 - "$DB" "$snap" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
d = sqlite3.connect(dst)
with d:
    s.backup(d)          # atomic copy of a consistent view, WAL frames included
s.close(); d.close()
PY

# 2. Compress, drop the uncompressed copy.
gzip -f "$snap"
echo "snapshot: $gz ($(du -h "$gz" | cut -f1))"

# 3. Rotate the local cache — keep the newest $KEEP.
mapfile -t old < <(ls -1t "$BACKUP_DIR"/readings-*.db.gz 2>/dev/null | tail -n +"$((KEEP + 1))")
if ((${#old[@]})); then
  printf '%s\n' "${old[@]}" | xargs -r rm -f
  echo "rotated: removed ${#old[@]} old local snapshot(s), keeping $KEEP"
fi

# 4. Upload to R2 (the off-box copy).
if [[ "$UPLOAD" == 0 ]]; then
  echo "--local: skipping R2 upload."
  exit 0
fi
if [[ -z "$R2_REMOTE" ]]; then
  echo "⚠  KP_R2_REMOTE not set — kept the local snapshot but did NOT push off-box." >&2
  echo "   Configure rclone (see deploy/README.md) and set KP_R2_REMOTE to enable." >&2
  exit 0
fi
if ! command -v rclone >/dev/null 2>&1; then
  echo "⚠  rclone not installed — local snapshot kept, no off-box copy. See deploy/README.md." >&2
  exit 0
fi
rclone copy "$gz" "$R2_REMOTE" --no-traverse
echo "uploaded: $(basename "$gz") -> $R2_REMOTE"
