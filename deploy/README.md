# Deploy — Raspberry Pi

The public site is two halves:

- **Frontend** — the Astro build in `web/`, hosted on **Cloudflare Pages**.
- **API** — the FastAPI service in `api/`, running on the **Pi** as a systemd
  service on `127.0.0.1:8000`, reachable only through the **Cloudflare Tunnel**.

## 1. Cloudflare Tunnel route  ✅ (done in the dashboard)

The tunnel is **remotely-managed** (installed once with a token; there is no
local `config.yml` or tunnel UUID). The route was added in the dashboard:

> Zero Trust → Networking → Tunnels → *(your tunnel)* → **Routes** →
> **Add route** → **Published application** →
> subdomain `api`, domain `kingstonpier.ca`, Service URL `http://localhost:8000`

Cloudflare created the `api.kingstonpier.ca` DNS record and routes it to the
Pi. `cloudflared` already runs as its own service — nothing to install or
restart here.

## 2. API service

One-time, on the Pi:

```bash
git clone <repo> ~/kingstonpier        # or wherever; the installer detects the path
cd ~/kingstonpier

# venv for the API (tiny — no torch)
python3 -m venv api/.venv
api/.venv/bin/pip install -r api/requirements.txt

# (optional) give it data before the tracker exists
api/.venv/bin/python api/seed.py

# install + start the systemd service (auto-detects user + repo path)
bash deploy/install.sh
```

`deploy/install.sh` stamps your user/path/port into
`systemd/kingstonpier-api.service`, installs it to
`/etc/systemd/system/kingstonpier-api.service`, and enables it (starts on boot,
restarts on failure). Preview the unit without touching the system:

```bash
bash deploy/install.sh --dry-run
```

### Verify

```bash
curl -s localhost:8000/healthz            # on the Pi
curl -s https://api.kingstonpier.ca/healthz   # from anywhere (through the tunnel)
journalctl -u kingstonpier-api -f         # logs
```

`/healthz` reports `hasData:false` until the tracker (or `seed.py`) has written
rows — that's expected; the API still serves a `live:false` payload.

### Update after a change

```bash
cd ~/kingstonpier && git pull
# if API deps changed: api/.venv/bin/pip install -r api/requirements.txt
sudo systemctl restart kingstonpier-api
```

## 3. Frontend (Cloudflare Pages)

Build `web/` and deploy to Pages (apex + `www`). The API base defaults to
`https://api.kingstonpier.ca` (baked into `web/src/lib/api.ts`), so no env var
is required in Pages unless you want to override it (`PUBLIC_API_BASE`). The
API's CORS allowlist already includes `kingstonpier.ca` and `www.` (configurable
via `KP_CORS_ORIGINS`).

## 4. CV worker (later)

`systemd/kingstonpier-cv-worker.service` is a **stub** until `tracker/` exists.
Once `python -m tracker.worker` is real and writing to `db/data/readings.db`,
install it the same way (it runs `Nice=10` so inference bursts don't starve the
existing site). Sanity-check that a full 5-feed pass fits inside the ~3 min
sampling interval on the Pi before enabling it.
