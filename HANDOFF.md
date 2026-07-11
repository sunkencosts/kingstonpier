# kingstonpier.ca — handoff / operations

**Status as of 2026-07-09: fully deployed and live.** Frontend, backend, CV
worker, public API, and nightly off-box backups are all running and
self-updating on push to `main`. This doc is the operator's map: what's live,
how deploys work, how to run it locally, and how to do the recurring jobs.

## Live system

| Piece | Where | Status |
|-------|-------|--------|
| Dashboard | `https://kingstonpier.ca` (+ `www`) | ✅ live |
| Public API | `https://api.kingstonpier.ca` (Cloudflare Tunnel → Pi `:8000`) | ✅ live |
| CV worker | Pi, samples 5 city webcams every ~3 min → density count → SQLite | ✅ live |
| DB | SQLite (WAL) on the Pi, `~/apps/kingstonpier/db/data/readings.db` | ✅ single source of truth |
| Nightly backup | Pi `03:30` → Cloudflare R2 `kingstonpier-backups` | ✅ verified |

The counter is a small frozen-MobileNetV3 density model, **CPU-only**
(torch/torchvision), val MAE ≈ 2.68 on 115 hand-labelled frames. No images are
ever stored or served — integer counts only.

## Deploy model (push to `main` = deploy)

Two halves, deployed two independent ways on every push to `main`:

- **Frontend** (`web/`) → **Cloudflare Workers Builds** (Git-connected to the
  `kingstonpier` Worker). Runs `npm run build` → `npx wrangler deploy` from
  `/web`. No Actions, no secrets in the repo. Config: `web/wrangler.toml`
  (assets-only Worker serving `web/dist`).
- **Backend** (`api/` + `tracker/`) → **self-hosted GitHub Actions runner** on
  the Pi (`.github/workflows/deploy.yml`, `runs-on: [self-hosted, kingstonpier]`).
  rsyncs source → `~/apps/kingstonpier`, installs deps, restarts services,
  smoke-checks `/healthz`.

**Never touched by CI** (git-ignored, live only on the Pi):
- the **DB** — history persists across deploys; backed up to R2.
- the **model** `tracker/counter_model.pt` — ships out-of-band via
  `tracker/deploy_model.sh <user@pi>` when you're happy with a retrain.

The Pi runs from a stable app dir **`~/apps/kingstonpier`** (holds the venvs, DB,
and model; CI rsyncs code in with `--delete` + excludes so those survive).

### The Pi has two runners
`~/actions-runner` (mirrorleague) and `~/actions-runner-kingstonpier` (this repo,
service `actions.runner.sunkencosts-kingstonpier.pi-kingstonpier`). Repo-scoped +
the `kingstonpier` label keep them from crossing over. If a deploy job sits
"queued" forever, that runner service is down — `sudo systemctl restart
actions.runner.sunkencosts-kingstonpier.pi-kingstonpier`.

## Local dev

```bash
./dev.sh          # tracker (--watch) + API (:8000) + dashboard (:4321), live counts
```

Opens the whole stack wired together at `http://localhost:4321`. It writes
`web/.env.development` (NOT `web/.env`) so the dev API URL can never leak into a
production build. One-time setup per tier (`uv sync` in `tracker/`, venv in
`api/`, `npm install` in `web/`) — `dev.sh` preflights and tells you the command.

## Recurring jobs

**Retrain the model** (as you label more frames):
1. `cd tracker && ./.venv/bin/python train_counter.py` — it backs up the current
   model to `counter_model.prev.pt`, then prints a BETTER/WORSE/SAME verdict vs
   the last run.
2. If better: `./deploy_model.sh <user@pi>` (scp + restart the worker). If worse:
   restore `counter_model.prev.pt`.

**Backups**: nightly automatically. Manually: `sudo systemctl start
kingstonpier-backup.service`. Verify: `rclone ls r2:kingstonpier-backups`.
Restore onto a fresh card: see `deploy/README.md` §5.

**Deploy code**: just push to `main`.

## Gotchas already solved (don't re-debug)

- **Tunnel origin must be `http://localhost:8000`**, not `https://` — TLS
  terminates at Cloudflare's edge; the origin hop is plain HTTP on loopback.
  `https://` origin → 502 "not a TLS handshake".
- **Never `uv sync`/`pyproject.toml` on the Pi** — it pins CUDA torch. The Pi
  uses `tracker/requirements-pi.txt` (`torch==2.13.0+cpu`) with a plain venv.
- **R2 backups need `no_check_bucket = true`** in the rclone remote — a
  bucket-scoped token can't `CreateBucket`, which rclone tries by default →
  403 on upload. Also use a **current rclone** (Raspbian's v1.60 hid the real
  error); install via `curl https://rclone.org/install.sh | sudo bash`.
- **CI smoke-check** uses `curl --retry-connrefused` because uvicorn takes ~6s to
  bind after systemd reports the unit active.

## Open follow-ups (nice-to-have, not blocking)

- **Busyness scale is now capacity-relative** — the API returns a `capacity`
  (the count that reads as "packed"), a one-way ratchet anchored at
  `KP_CAPACITY_PRIOR` (default 500 — the physical estimate of a full pier) that
  only rises to track a genuinely busier observed peak (`aggregate.capacity`).
  `busyness.ts` bands and the popular-times bar heights are fractions of it, so
  a ~150 reading now reads "Moderate", not "Packed". Tune `KP_CAPACITY_PRIOR`
  (env) if 500 is off; the bands themselves shouldn't need re-tuning as counts
  grow. `lo/hi` (±15%) is unchanged.
- **Worker logging is sparse** — add `Environment=PYTHONUNBUFFERED=1` to
  `systemd/kingstonpier-cv-worker.service` if you want per-pass "sampled N feeds"
  lines in `journalctl`.
- **Node 20 deprecation warning** on `actions/checkout@v4` — cosmetic; GitHub
  force-runs it on Node 24. Bump when convenient.
- **`trend`/`popularByDay` fill in over time** — mostly zeros until a few days of
  history accumulate.

## Key paths

- Deploy details: `deploy/README.md` · go-live steps: `deploy/CHECKLIST.md`
- Systemd units + installer: `systemd/`, `deploy/install.sh`
- Model + labelling/training loop: `tracker/README.md`
- API contract (the `readings` schema): `db/schema.sql`
