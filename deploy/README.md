# Deploy — Raspberry Pi + Cloudflare

The public site is two halves, deployed two ways on every push to `main`:

- **Frontend** (`web/`) → **Cloudflare** as a static-assets Worker, built by
  Cloudflare's Git integration (no Actions, no secrets). See §4.
- **Backend** (`api/` + `tracker/`) → the **Pi**, by a **self-hosted GitHub
  Actions runner** (`.github/workflows/deploy.yml`), same pattern as mirrorleague.

Two things are **git-ignored and never deployed by CI**, by design:

- **the DB** (`db/data/readings.db`) — lives only on the Pi; history persists
  across deploys (§5 backs it up off-box).
- **the model** (`tracker/counter_model.pt`) — ships out-of-band via
  `tracker/deploy_model.sh` when you're happy with a retrain (see tracker README).

The app runs from a stable dir, **`~/apps/kingstonpier`** (matches mirrorleague's
`~/apps/<name>`). CI rsyncs code there; the DB, venvs, and model live there and
are never clobbered.

---

## 1. Cloudflare Tunnel route  ✅ (done in the dashboard)

Remotely-managed tunnel (token install; no local `config.yml`/UUID). Route added:

> Zero Trust → Networking → Tunnels → *(your tunnel)* → **Routes** → **Add route**
> → **Published application** → subdomain `api`, domain `kingstonpier.ca`,
> Service URL `http://localhost:8000`

Cloudflare owns the `api.kingstonpier.ca` DNS + routing; `cloudflared` already
runs as its own service.

## 2. One-time Pi bootstrap

CI only *updates* an already-set-up box, so do this once by hand.

```bash
# a) Self-hosted runner for THIS repo (GitHub → repo Settings → Actions → Runners
#    → New self-hosted runner). A repo-scoped runner only serves its own repo, so
#    this is separate from any mirrorleague runner — use its own directory. The
#    'kingstonpier' label MUST match `runs-on: [self-hosted, kingstonpier]`.
mkdir -p ~/actions-runner-kingstonpier && cd ~/actions-runner-kingstonpier
# (download + extract the runner tarball per the GitHub page, then:)
./config.sh --url https://github.com/<you>/kingstonpier --token <...> \
  --name pi-kingstonpier --labels kingstonpier
sudo ./svc.sh install && sudo ./svc.sh start

# b) Let the runner restart the services without a password prompt:
echo "$USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart kingstonpier-*" \
  | sudo tee /etc/sudoers.d/kingstonpier   # adjust the systemctl path if `which systemctl` differs

# c) Seed the app dir + venvs (CI also creates venvs, but the units need to exist
#    before CI's restart step, so install them now):
git clone <repo> ~/apps/kingstonpier && cd ~/apps/kingstonpier
python3 -m venv api/.venv     && api/.venv/bin/pip install -r api/requirements.txt
python3 -m venv tracker/.venv && tracker/.venv/bin/pip install -r tracker/requirements-pi.txt

# d) Copy the trained model over (git-ignored — from your dev box):
#    scp tracker/counter_model.pt <pi>:~/apps/kingstonpier/tracker/

# e) Install + start all units (API + worker + nightly backup timer):
bash deploy/install.sh
```

> ⚠️ **Never `uv sync` / use `pyproject.toml` on the Pi** — it pins torch to the
> CUDA-13 index (no aarch64/CPU wheels). The Pi uses `requirements-pi.txt` with a
> plain venv. Needs 64-bit Raspberry Pi OS (aarch64).

`deploy/install.sh` stamps your user/path/port into the unit templates, installs
them to `/etc/systemd/system/`, and enables them. Targets: `api`, `worker`,
`backup`, or all (default). Preview with `--dry-run`.

### Verify

```bash
curl -s localhost:8000/healthz                 # on the Pi
curl -s https://api.kingstonpier.ca/healthz    # through the tunnel
journalctl -u kingstonpier-cv-worker -f        # worker sampling every 3 min
```

`/healthz` reports `hasData:false` until the worker writes its first row — that's
expected; the API serves a `live:false` payload meanwhile (never 500s).

> **Before trusting the worker:** time one 5-feed pass on the Pi (torch is heavier
> than the old plan). Run `tracker/.venv/bin/python crowd_tracker.py --no-db` and
> confirm it finishes well inside the 3-minute interval; if not, raise `--watch 3`
> to a larger number.

## 3. Continuous deploy (GitHub Actions → Pi)

Once bootstrapped, **push to `main`** and `.github/workflows/deploy.yml` (on the
self-hosted runner) does the rest:

1. rsync source → `~/apps/kingstonpier/` (excludes `db/data/`, both `.venv/`, the
   model, `dataset/`, and `web/` — none of which belong to CI).
2. `pip install` the API deps (tiny) every run; reinstall the tracker's CPU-torch
   stack **only when `requirements-pi.txt` changed** (torch is huge — a content
   hash gates it).
3. `sudo systemctl restart kingstonpier-api kingstonpier-cv-worker` + a
   `/healthz` smoke check.

It never touches the DB or the model. To ship a **new model**, retrain and run
`tracker/deploy_model.sh <user@pi>` from your dev box (see the tracker README).

## 4. Frontend — Cloudflare (Workers Static Assets, Git-connected)

The dashboard is pure static (Astro SSG → `web/dist`), served as an **assets-only
Worker** (Cloudflare's current "Workers Builds" flow; the classic Pages create UI
is being retired). Config lives in `web/wrangler.toml` (`[assets] directory =
"./dist"` — no Worker script).

Connect once in the dashboard (**Workers & Pages → Create → Import a
repository**), pointing at this repo:

- **Build command:** `npm run build`
- **Deploy command:** `npx wrangler deploy`
- **Path:** `/web`  (working dir → the build and `wrangler.toml` resolve here)
- **API token:** *Create new token* (the wizard scopes it for Worker deploys)

Cloudflare then builds + deploys on every push to `main` — no Actions job. After
the first deploy, attach the domain: **the Worker → Settings → Domains & Routes →
Add → Custom Domain →** `kingstonpier.ca` and `www.kingstonpier.ca`.

The API base defaults to `https://api.kingstonpier.ca` (baked into
`web/src/lib/api.ts`), so no build env var is needed; the API's CORS allowlist
already includes `kingstonpier.ca`/`www.` (override via `KP_CORS_ORIGINS`).

## 5. Off-box DB backups → Cloudflare R2

The DB is the **only** copy of your accumulated history and it is **not in git**,
so it's backed up off the SD card to **Cloudflare R2** nightly.
`deploy/backup_db.sh` takes a consistent online SQLite snapshot (safe while the
worker writes), gzips it, keeps a small rotated local cache, and uploads to R2 via
`rclone`. `kingstonpier-backup.timer` runs it daily at 03:30.

**Configure R2 (once):**

```bash
# 1) In the Cloudflare dashboard: R2 → create bucket "kingstonpier-backups",
#    then create an R2 API token (Object Read & Write).
# 2) Install + configure rclone on the Pi with an S3-compatible remote named "r2":
sudo apt install rclone   # or: curl https://rclone.org/install.sh | sudo bash
rclone config
#    type = s3 ; provider = Cloudflare ; access_key_id / secret_access_key from the token ;
#    endpoint = https://<accountid>.r2.cloudflarestorage.com ; region = auto
```

The `kingstonpier-backup.service` sets `KP_R2_REMOTE=r2:kingstonpier-backups`
(and `KP_BACKUP_KEEP=14`). If rclone/R2 aren't set up yet, the backup **still
runs** and keeps a local snapshot — it just skips the upload and says so, so it's
safe to install the timer before configuring R2.

```bash
sudo systemctl start kingstonpier-backup.service   # run one now
systemctl list-timers kingstonpier-backup          # next scheduled run
rclone ls r2:kingstonpier-backups                  # confirm the off-box copy
```

**Restore** (e.g. onto a fresh SD card):

```bash
rclone copy r2:kingstonpier-backups/readings-<stamp>.db.gz .   # or use a local cache copy
gunzip readings-<stamp>.db.gz
sudo systemctl stop kingstonpier-cv-worker
cp readings-<stamp>.db ~/apps/kingstonpier/db/data/readings.db
sudo systemctl start kingstonpier-cv-worker        # WAL re-establishes on first write
```
