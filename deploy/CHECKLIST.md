# Go-live checklist — Pi + Cloudflare

Ordered so the first automated deploy is green. Labels: 💻 dev box · ☁️
Cloudflare/GitHub dashboard · 🍓 Pi. Details in [`deploy/README.md`](README.md).

> **App dir:** everything on the Pi lives in **`~/apps/kingstonpier`** — the path
> the deploy workflow rsyncs to and the systemd units point at. If you cloned /
> installed a venv somewhere else, `mv` it there before starting.

## Phase 0 — Push to `main` first

- [ ] **💻 Commit + push all local changes to `main`.** CI reads these *from
      `main`*, so they must be there before the runner picks up a job:
      - `tracker/requirements-pi.txt` (the **CPU-torch fix** — else CI reinstalls
        the CUDA/nvidia junk)
      - `web/wrangler.toml` (Cloudflare needs it to deploy the site)
      - `.github/workflows/deploy.yml` (the `kingstonpier` runner label)
      - the doc updates

## Phase 1 — Cloudflare

- [ ] **☁️ Frontend (Workers Static Assets):** Workers & Pages → Create → **Import
      a repository** → this repo. **Build** `npm run build`, **Deploy**
      `npx wrangler deploy`, **Path** `/web`, **API token** → *Create new* →
      Deploy. (Serves `web/dist` via `web/wrangler.toml`.)
- [ ] **☁️ Custom domain:** that Worker → Settings → Domains & Routes → Add →
      **Custom Domain** → `kingstonpier.ca` **and** `www.kingstonpier.ca`.
- [ ] **☁️ R2 backup bucket:** R2 → create bucket **`kingstonpier-backups`** →
      create an **R2 API token** (Object Read & Write). Keep the keys + account ID.

## Phase 2 — Pi bootstrap (one-time; register the runner LAST)

- [ ] **🍓 Confirm 64-bit OS:** `uname -m` → **`aarch64`**.
- [ ] **🍓 App dir:** `git clone <repo> ~/apps/kingstonpier && cd ~/apps/kingstonpier`
      (or `mv` your existing clone here).
- [ ] **🍓 Create venvs** (needed before `install.sh` preflights them):
      ```bash
      python3 -m venv api/.venv     && api/.venv/bin/pip install -r api/requirements.txt
      python3 -m venv tracker/.venv && tracker/.venv/bin/pip install -r tracker/requirements-pi.txt
      ```
      `requirements-pi.txt` pins `torch==2.13.0+cpu` — **CPU only, no nvidia**.
- [ ] **💻 Copy the model to the Pi** (git-ignored, not in the clone):
      `scp tracker/counter_model.pt <pi>:~/apps/kingstonpier/tracker/`
- [ ] **🍓 Time one inference pass:** `tracker/.venv/bin/python crowd_tracker.py --no-db`
      — must finish well under 3 min (else raise `--watch 3` in the worker unit).
- [ ] **🍓 rclone → R2:** `sudo apt install rclone && rclone config` → remote
      **named `r2`**, type `s3`, provider `Cloudflare`, your token's keys, endpoint
      `https://<accountid>.r2.cloudflarestorage.com`, region `auto`. Test:
      `rclone lsd r2:`
- [ ] **🍓 Install the services** (API + worker + backup timer):
      `bash deploy/install.sh`
- [ ] **🍓 sudoers for CI restarts:**
      ```bash
      echo "$USER ALL=(root) NOPASSWD: $(which systemctl) restart kingstonpier-*" | sudo tee /etc/sudoers.d/kingstonpier
      ```
- [ ] **🍓 Register the kingstonpier runner (LAST):** it's separate from the
      mirrorleague runner — a repo-scoped runner only serves its own repo. Get the
      token from GitHub → repo **Settings → Actions → Runners → New self-hosted
      runner (Linux / ARM64)**, then in its **own directory**:
      ```bash
      mkdir -p ~/actions-runner-kingstonpier && cd ~/actions-runner-kingstonpier
      curl -o actions-runner.tar.gz -L <url-from-that-page> && tar xzf actions-runner.tar.gz
      ./config.sh --url https://github.com/sunkencosts/kingstonpier \
        --token <TOKEN> --name pi-kingstonpier --labels kingstonpier
      sudo ./svc.sh install && sudo ./svc.sh start
      ```
      > The `--labels kingstonpier` **must** match `runs-on: [self-hosted,
      > kingstonpier]` in the workflow, or the job won't be picked up.

Once the runner starts, it grabs the pending job and deploys — green, because the
services already exist.

## Phase 3 — Verify

- [ ] **🍓 API:** `curl -s localhost:8000/healthz`
- [ ] **🌐 Tunnel:** `curl -s https://api.kingstonpier.ca/healthz`
- [ ] **🍓 Worker:** `journalctl -u kingstonpier-cv-worker -f` → a 5-feed pass every
      ~3 min; then `curl -s https://api.kingstonpier.ca/now` → `"live": true`.
- [ ] **🌐 Dashboard:** `https://kingstonpier.ca` renders the live count.
- [ ] **🍓 Backup:** `sudo systemctl start kingstonpier-backup.service` then
      `rclone ls r2:kingstonpier-backups` (a `.gz` appears);
      `systemctl list-timers kingstonpier-backup` shows the nightly run.

## Phase 4 — Ongoing (automatic)

- [ ] **Code:** push to `main` → the kingstonpier runner redeploys the Pi;
      Cloudflare rebuilds the site. ✅
- [ ] **New model:** retrain on 💻, then `tracker/deploy_model.sh <user@pi>`. CI
      never touches the DB or model.

## Watch-outs

- The runner **must** be labelled `kingstonpier` (repo-scoped runners already
  can't cross over, but the label makes it explicit + future-proofs org runners).
- Two runners on one Pi can run jobs concurrently — negligible for occasional
  deploys.
- Once real data accumulates, retune `web/src/lib/busyness.ts` thresholds — they
  were set to the synthetic scale (a ~120-people reading pegged "packed").
