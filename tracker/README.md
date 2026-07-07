# tracker/ — CV worker + data store (planned)

Not built yet. Refactor of the existing `crowd-tracker` CLI prototype:

- `core.py` — reusable detection core (`FEEDS`, `Detector`, `fetch_frame`,
  `count_people`, `busyness`) shared by the CLI and the worker.
- `worker.py` — persistent sampling loop (~3 min cadence, staggered feeds)
  writing integer counts to SQLite. Runs as a `systemd` service, `Nice`d.
- `db.py` — SQLite schema (`readings`: ts, per-feed counts, total, feeds_ok)
  and read/write helpers.

Pi model config: `yolov8s@960` exported to NCNN, no TTA. **Integer counts only,
no image blobs** — that is the privacy stance.
