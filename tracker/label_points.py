#!/usr/bin/env python3
"""Point-and-click crowd-counting labeller.

Serves the collected frames in your browser. Click each person once (on their
head) to drop a point; click a point again to remove it. The running count is
the label. Points are saved as one JSON file per image under dataset/points/,
ready to train a crowd-density counter.

Run:
    python label_points.py                 # serve dataset/images on :8000
    python label_points.py --port 8080

Then open http://localhost:8000 in a browser. On WSL2 your Windows browser
reaches it via localhost. Keys: A/D or arrows = prev/next image, they autosave.
"""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from feeds import HERE

IMAGES_DIR = HERE / "dataset" / "images"
POINTS_DIR = HERE / "dataset" / "points"

PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Crowd labeller</title>
<style>
  body { margin:0; font:14px system-ui, sans-serif; display:flex; height:100vh; }
  #side { width:230px; overflow-y:auto; border-right:1px solid #ccc; padding:8px;
          box-sizing:border-box; }
  #side .item { padding:4px 6px; cursor:pointer; border-radius:4px;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #side .item:hover { background:#eef; }
  #side .item.active { background:#dde; font-weight:bold; }
  #side .done { color:#2a7; }
  #side .cand { color:#c80; }
  #main { flex:1; display:flex; flex-direction:column; align-items:center;
          padding:10px; box-sizing:border-box; overflow:auto; }
  #bar { margin-bottom:8px; }
  #count { font-size:20px; font-weight:bold; }
  canvas { border:1px solid #999; cursor:crosshair; image-rendering:pixelated; }
  button { font-size:14px; padding:4px 10px; margin:0 3px; }
  .hint { color:#666; margin-left:12px; }
</style></head><body>
<div id="side"></div>
<div id="main">
  <div id="bar">
    <button onclick="nav(-1)">◀ Prev (A)</button>
    <button onclick="nav(1)">Next (D) ▶</button>
    <span id="count">0 people</span>
    <span id="prog" class="hint"></span>
    <span class="hint">click head = add · click dot = remove · candidates are model guesses</span>
  </div>
  <canvas id="cv"></canvas>
</div>
<script>
const SCALE = 2;            // display frames at 2x so small people are clickable
const HIT = 3;             // click within this many image-px of a dot removes it
let list = [], idx = 0, cur = null, pts = [], img = new Image();
const cv = document.getElementById('cv'), ctx = cv.getContext('2d');

async function loadList() {
  list = await (await fetch('/api/list')).json();
  renderSide();
  const firstUnlabelled = list.findIndex(x => !x.labeled);
  show(firstUnlabelled >= 0 ? firstUnlabelled : 0);
}

function renderSide() {
  const s = document.getElementById('side');
  s.innerHTML = '';
  list.forEach((it, i) => {
    const d = document.createElement('div');
    d.className = 'item' + (i === idx ? ' active' : '');
    const mark = it.labeled ? '<span class="done">✓</span> '
               : it.candidate ? '<span class="cand">•</span> ' : '';
    d.innerHTML = mark + it.name;
    d.onclick = () => show(i);
    s.appendChild(d);
  });
  const done = list.filter(x => x.labeled).length;
  document.getElementById('prog').textContent = `${done}/${list.length} labelled`;
}

async function show(i) {
  if (i < 0 || i >= list.length) return;
  idx = i; cur = list[i].name;
  const data = await (await fetch('/api/points/' + encodeURIComponent(cur))).json();
  pts = data.points || [];
  img.onload = draw;
  img.src = '/img/' + encodeURIComponent(cur) + '?t=' + Date.now();
  renderSide();
}

function draw() {
  cv.width = img.width * SCALE; cv.height = img.height * SCALE;
  ctx.drawImage(img, 0, 0, cv.width, cv.height);
  for (const [x, y] of pts) {
    ctx.beginPath();
    ctx.arc(x * SCALE, y * SCALE, 5, 0, 7);
    ctx.fillStyle = 'rgba(255,40,40,0.85)';
    ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = 'white'; ctx.stroke();
  }
  document.getElementById('count').textContent = pts.length + ' people';
}

cv.onclick = (e) => {
  const r = cv.getBoundingClientRect();
  const x = (e.clientX - r.left) / SCALE, y = (e.clientY - r.top) / SCALE;
  const hit = pts.findIndex(([px, py]) => Math.hypot(px - x, py - y) < HIT);
  if (hit >= 0) pts.splice(hit, 1);
  else pts.push([Math.round(x), Math.round(y)]);
  draw();
};

async function save() {
  if (cur === null) return;
  await fetch('/api/points/' + encodeURIComponent(cur), {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({points: pts, image_w: img.width, image_h: img.height})
  });
  const it = list[idx]; it.labeled = true; it.candidate = false;
}

async function nav(delta) { await save(); show(idx + delta); }

document.onkeydown = (e) => {
  if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'd') nav(1);
  else if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'a') nav(-1);
};
window.onbeforeunload = save;
loadList();
</script></body></html>
"""


def _safe_rel(raw: str) -> Path | None:
    """Resolve a request path to a relative jpg under IMAGES_DIR, or None."""
    rel = unquote(raw).lstrip("/")
    if not re.fullmatch(r"[\w./\- :T]+\.jpg", rel):
        return None
    target = (IMAGES_DIR / rel).resolve()
    if IMAGES_DIR.resolve() not in target.parents:
        return None
    return Path(rel)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/list":
            return self._send(200, json.dumps(self._list()))
        if self.path.startswith("/api/points/"):
            rel = _safe_rel(self.path[len("/api/points/"):])
            if rel is None:
                return self._send(400, '{"error":"bad path"}')
            return self._send(200, json.dumps(self._read_points(rel)))
        if self.path.startswith("/img/"):
            rel = _safe_rel(self.path[len("/img/"):].split("?")[0])
            if rel is None or not (IMAGES_DIR / rel).exists():
                return self._send(404, b"not found", "text/plain")
            return self._send(200, (IMAGES_DIR / rel).read_bytes(), "image/jpeg")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self.path.startswith("/api/points/"):
            return self._send(404, b"not found", "text/plain")
        rel = _safe_rel(self.path[len("/api/points/"):])
        if rel is None:
            return self._send(400, '{"error":"bad path"}')
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or "{}")
        out = (POINTS_DIR / rel).with_suffix(".json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "points": data.get("points", []),
            "image_w": data.get("image_w"),
            "image_h": data.get("image_h"),
            "candidate": False,
        }))
        self._send(200, '{"ok":true}')

    # --- helpers ---
    def _list(self):
        items = []
        for img in sorted(IMAGES_DIR.glob("**/*.jpg")):
            rel = img.relative_to(IMAGES_DIR)
            pf = (POINTS_DIR / rel).with_suffix(".json")
            labeled = candidate = False
            if pf.exists():
                candidate = json.loads(pf.read_text()).get("candidate", False)
                labeled = not candidate
            items.append({"name": str(rel), "labeled": labeled, "candidate": candidate})
        # Unlabelled (incl. candidates) first, so you don't click through done ones.
        items.sort(key=lambda x: (x["labeled"], x["name"]))
        return items

    def _read_points(self, rel: Path):
        pf = (POINTS_DIR / rel).with_suffix(".json")
        if pf.exists():
            return json.loads(pf.read_text())
        return {"points": []}


def main() -> int:
    parser = argparse.ArgumentParser(description="Point-and-click crowd labeller.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not IMAGES_DIR.exists():
        print(f"No images at {IMAGES_DIR}. Run collect_frames.py first.")
        return 1

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Labelling {len(list(IMAGES_DIR.glob('**/*.jpg')))} frames.")
    print(f"Open http://localhost:{args.port} in your browser. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
