# Go-live checklist — Pi + Cloudflare

Ordered so the first automated deploy doesn't fail. Labels show where each step
runs: 💻 dev box · ☁️ Cloudflare/GitHub dashboard · 🍓 Pi. Full detail in
[`deploy/README.md`](README.md).

## Phase 1 — Merge & Cloudflare (do first)

- [ ] **💻 Merge the branch → `main`** (open a PR, merge it). CI (`deploy.yml`)
      and Pages both key off `main`, and the workflow only exists on `main` once
      merged.
- [ ] **☁️ Cloudflare — connect the repo (Workers Builds / Static Assets):**
      Workers & Pages → Create → **Import a repository** → this repo. Fill:
      **Build command** `npm run build`, **Deploy command** `npx wrangler deploy`,
      **Path** `/web`, then **Create new token** → Deploy. Serves `web/dist` as a
      static-assets Worker (config in `web/wrangler.toml`). No env var needed —
      the API base is baked in.
- [ ] **☁️ Attach the custom domain:** the new Worker → Settings → Domains &
      Routes → Add → **Custom Domain** → `kingstonpier.ca` **and**
      `www.kingstonpier.ca`.
- [ ] **☁️ Cloudflare R2 — create the backup target:** R2 → create bucket
      **`kingstonpier-backups`** → create an **R2 API token** (Object Read &
      Write). Save the access key / secret / account ID for the Pi step.

## Phase 2 — Pi bootstrap (one-time, mostly manual)

- [ ] **🍓 Confirm 64-bit OS:** `uname -m` must print **`aarch64`** (32-bit ARM
      can't install torch).
- [ ] **🍓 Clone to the app dir:**
      `git clone <repo> ~/apps/kingstonpier && cd ~/apps/kingstonpier`
- [ ] **🍓 Create venvs:**
      ```bash
      python3 -m venv api/.venv     && api/.venv/bin/pip install -r api/requirements.txt
      python3 -m venv tracker/.venv && tracker/.venv/bin/pip install -r tracker/requirements-pi.txt
      ```
- [ ] **💻 Copy the model to the Pi** (git-ignored, so it's not in the clone):
      ```bash
      scp tracker/counter_model.pt <pi>:~/apps/kingstonpier/tracker/
      ```
- [ ] **🍓 Time one inference pass** (the torch caveat):
      `tracker/.venv/bin/python crowd_tracker.py --no-db` — must finish well under
      3 min. If not, bump `--watch 3` higher in
      `systemd/kingstonpier-cv-worker.service`.
- [ ] **🍓 Configure rclone for R2:** `sudo apt install rclone && rclone config`
      → new remote **named `r2`**, type `s3`, provider `Cloudflare`, your token's
      keys, endpoint `https://<accountid>.r2.cloudflarestorage.com`, region
      `auto`. Verify: `rclone lsd r2:`
- [ ] **🍓 Install the services** (API + worker + backup timer):
      `bash deploy/install.sh`
- [ ] **🍓 sudoers for CI restarts:**
      ```bash
      echo "$USER ALL=(root) NOPASSWD: $(which systemctl) restart kingstonpier-*" | sudo tee /etc/sudoers.d/kingstonpier
      ```
- [ ] **🍓 Register the self-hosted runner** for *this* repo (GitHub → repo
      Settings → Actions → Runners → New self-hosted runner). Install as a service
      so it survives reboots:
      ```bash
      cd ~/actions-runner && ./config.sh --url https://github.com/<you>/kingstonpier --token <...>
      sudo ./svc.sh install && sudo ./svc.sh start
      ```
      > A runner is per-repo — mirrorleague's won't pick these up. Same Pi, second
      > runner is fine.

## Phase 3 — Verify end-to-end

- [ ] **🍓 API up:** `curl -s localhost:8000/healthz`
- [ ] **🌐 Tunnel:** `curl -s https://api.kingstonpier.ca/healthz` (from anywhere)
- [ ] **🍓 Worker writing:** `journalctl -u kingstonpier-cv-worker -f` → a 5-feed
      pass every ~3 min; then `curl -s https://api.kingstonpier.ca/now` shows
      `"live": true` with a real total.
- [ ] **🌐 Dashboard:** open `https://kingstonpier.ca` → live count renders.
- [ ] **🍓 Backup works:** `sudo systemctl start kingstonpier-backup.service` then
      `rclone ls r2:kingstonpier-backups` (a `.gz` appears);
      `systemctl list-timers kingstonpier-backup` shows the nightly schedule.

## Phase 4 — Ongoing (no more manual deploys)

- [ ] **Code:** push to `main` → runner redeploys the Pi + Pages rebuilds. ✅
- [ ] **New model:** retrain on 💻, then `tracker/deploy_model.sh <user@pi>` (scp
      + restart). The DB and model are never touched by CI.

## Watch-outs

- The very first push-to-`main` may show a red CI run if the runner/units weren't
  ready yet — just re-run it after Phase 2.
- Once real data accumulates, retune `web/src/lib/busyness.ts` thresholds — they
  were set to the synthetic scale (a ~120-people reading pegged "packed").
