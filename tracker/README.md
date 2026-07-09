# tracker/ — Breakwater Park crowd worker + labelling pipeline

Samples the City of Kingston's **Breakwater Park** webcam, counts the people
with a locally-trained crowd model, and appends one integer-count row per pass
to a SQLite `readings` table — the contract the sibling [`../api`](../api)
service reads to drive the dashboard. Counts only; no images are stored.

The "webcam" is really **five cameras** (Pier 1–5) behind a single Ozolio
player. Each has a plain snapshot URL returning a fresh ~640×360 JPEG:

```
https://relay.ozolio.com/pub.api?cmd=snap&oid=<camera id>
```

```
Camera: Breakwater Park, Kingston  ->  /home/bpalmer/code/kingstonpier/db/data/readings.db
  Pier 1   |   43 people
  Pier 2   |   31 people
  Pier 3   |   10 people
  Pier 4   |   24 people
  Pier 5   |    5 people
  TOTAL    |  113 people
```

## The counter

Counting is done by a small **density model** trained on this camera's own
frames (see the labelling pipeline below). It predicts a density map that sums
to the person count, which — unlike an object detector — reliably counts the
**sitting/lying sunbathers** and **small distant figures** a busy beach is full
of. On the first 50 labelled frames it hit ~3.5 people/frame error on held-out
timestamps, versus ~14 for a YOLO detector. Retrain any time with more data by
re-running `train_counter.py`.

## Setup

Local dev uses **uv** (`pyproject.toml` → `.venv`). torch/torchvision are pinned
to the CPU wheel index — there's no usable GPU here, and it keeps `.venv` small
and close to the Pi's:

```bash
cd ~/code/kingstonpier/tracker
uv sync                     # runtime deps -> .venv
uv sync --extra label       # + ultralytics, only when pre-seeding labels
```

> The **Pi** installs differently — plain `pip` + `requirements-pi.txt` (CPU
> aarch64), never `uv sync`/`pyproject.toml`. See [`../deploy/README.md`](../deploy/README.md).

You need a trained `counter_model.pt` before the tracker will run — either train
one (below) or drop in an existing file.

## Running the tracker

```bash
./.venv/bin/python crowd_tracker.py            # count every feed once, write a row
./.venv/bin/python crowd_tracker.py --watch 3  # keep sampling every 3 minutes
./.venv/bin/python crowd_tracker.py --no-db    # print only, don't write
./.venv/bin/python crowd_tracker.py --image dataset/images/pier_1/<frame>.jpg
./beach --watch 3                              # same, via the .venv wrapper
```

Rows go to the SQLite `readings` table (schema mirrors [`../db/schema.sql`](../db/schema.sql)).
By default the tracker writes `../db/data/readings.db` — the exact file the API
reads — so the two are wired together with no configuration. Override the
location with `KP_DB_PATH` (the API honours the same variable) if you keep the
store elsewhere.

## Labelling & training pipeline

The model learns from point labels — a click on each person's head, not drawn
boxes. Four scripts:

```bash
# 1. Collect frames across sunny days (leave it watching for variety)
./.venv/bin/python collect_frames.py --watch 15

# 2. Pre-seed candidate head-points from a YOLO detector (optional, saves clicks)
uv sync --extra label                        # preseed needs ultralytics (labelling-only)
./.venv/bin/python preseed_points.py

# 3. Label in the browser: click each head, click a dot to remove it
./.venv/bin/python label_points.py           # open http://localhost:8000

# 4. Train (holds out 2 rounds to validate, saves counter_model.pt)
./.venv/bin/python train_counter.py
```

Steps 2–3 are wrapped by `./label` (mirrors `./beach`): it pre-seeds any new
frames, then opens the labeller. `./label --collect` grabs one fresh round
first; extra args pass through to the pre-seeder (e.g. `./label --conf 0.15`).

Everything lands under `dataset/` (git-ignored): frames in `dataset/images/`,
one JSON of points per frame in `dataset/points/`. Pre-seeding places the people
a detector *can* find (orange `•` candidates) so you mostly add the lying-down
folks it missed. Near-black night frames are skipped at collection and
pre-seeding (same `DARK_LUMA_THRESHOLD` the counter trains on), so you never
label a frame training would discard. On WSL2, open the labeller in your Windows
browser via `localhost`; unlabelled frames sort first, and `A`/`D` move between
them and autosave. Aim for ~50–100 varied frames (crowd levels / times of day);
the fixed camera angle means that's enough.

`train_counter.py` reports its held-out error next to a YOLO detector's on the
same frames, so you can see it's actually better. It's a frozen MobileNetV3
encoder with a small trained density head — only the head learns, so it trains
on CPU in a few minutes without overfitting a small set.

## Retraining & deploying a new model

Every `train_counter.py` run **overwrites `counter_model.pt`** with the best
model *of that run* — even if it turns out worse than what you had. Two guards
make that safe:

- Before overwriting, the old model is copied to **`counter_model.prev.pt`**.
- The run ends with a **verdict** comparing the new held-out MAE to the previous
  run (from `train_log.jsonl`) and tells you whether to deploy or roll back.

The loop after a training session:

```bash
# 1. Retrain (add labels first if you have them)
./.venv/bin/python train_counter.py
#    -> reads the verdict: BETTER / WORSE / ABOUT THE SAME vs the last run

# 2a. WORSE and you don't want it — roll back to the prior model:
mv counter_model.prev.pt counter_model.pt

# 2b. BETTER (or good enough) — sanity-check the live counts:
./beach --no-db                    # 5-feed pass, no DB write; numbers look sane?

# 3. Deploy to the Pi (the model is git-ignored, so this scp is the only path):
./deploy_model.sh <user@pi-host>   # scp counter_model.pt + restart the worker
#    or set KP_PI_HOST once and just run ./deploy_model.sh

# 4. Verify it's live:
curl -s https://api.kingstonpier.ca/now    # live:true, sane total
```

`train_log.jsonl` (git-ignored) is your history: one line per run with frame
count and val MAE, so you can see whether more labelling is still lowering the
error. `counter_model.prev.pt` is git-ignored too (only ever one deep — it's a
rollback, not a version history).

## Files

| File | Role |
|------|------|
| `crowd_tracker.py` | The sampling worker: fetch feeds → count → append a `readings` row |
| `counter_model.py` | Density model, density-map maths, data loading, inference |
| `db.py` | The `readings` SQLite store (the API contract) |
| `feeds.py` | Feed list + snapshot fetcher (dependency-light) |
| `collect_frames.py` | Save raw frames into `dataset/` (skips near-black frames) |
| `label_points.py` | Browser point-click labeller |
| `preseed_points.py` | Seed candidate points from a detector (skips near-black frames) |
| `./label` | Wrapper: pre-seed new frames → open the labeller (`--collect` grabs a round first) |
| `./beach` | Wrapper: run the sampling worker with the project venv |
| `detector.py` | YOLO — used **only** for pre-seeding and the training baseline |
| `train_counter.py` | Train / validate the density counter; verdict + `.prev.pt` backup |
| `deploy_model.sh` | Push a new `counter_model.pt` to the Pi + restart the worker |
| `requirements-pi.txt` | CPU/ARM runtime deps for the Pi (not used locally — see deploy) |

`ultralytics` (YOLO) is only needed for the labelling pipeline; the runtime
tracker just needs `torch`/`torchvision`. The pre-seed detector is a community
VisDrone checkpoint — `detector.py` prints the one-time download command if the
weights are missing.

## Notes & limitations

- The five cameras cover the piers and beach from fixed angles — people in view,
  not every square metre of sand. Views can overlap and double-count someone
  between two cameras, so treat the total as a strong *relative* gauge. (The API
  serves the combined total and hides per-feed counts for this reason.)
- Source frames are only 640×360, so very small, hazy figures far across the
  water can still be missed — a hard floor the model can't fully clear.
- Night frames are near-black infrared; counts are only meaningful in daylight.
  The tracker gates on mean frame brightness (`DARK_LUMA_THRESHOLD` in
  `counter_model.py`): dark feeds record no reading rather than a hallucinated
  count, and dark frames are dropped from training/validation. At night, when
  every feed is dark, no row is written and the API's "live" flag goes false.
- Busy-ness labels, trends, and "popular times" are the API/frontend's job — the
  tracker only produces the raw integer counts.
