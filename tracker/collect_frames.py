#!/usr/bin/env python3
"""Collect raw webcam frames into a dataset for crowd-counting.

Grabs a fresh snapshot from each of the five Breakwater Park feeds and saves it
under dataset/images/<feed>/<timestamp>.jpg. Run it a few times across a sunny
day (or with --watch) to build up a set of frames at different crowd levels,
then label them with label_points.py.

Usage:
    python collect_frames.py                 # one snapshot from every feed, now
    python collect_frames.py --watch 15      # keep grabbing every 15 minutes
    python collect_frames.py --watch 15 --rounds 20   # 20 rounds then stop
"""
import argparse
import sys
import time
from datetime import datetime

from feeds import FEEDS, fetch_frame, slug, HERE

IMAGES_DIR = HERE / "dataset" / "images"


def grab_round() -> int:
    """Fetch one frame from every feed; return how many were saved."""
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    saved = 0
    for name, oid in FEEDS:
        out_dir = IMAGES_DIR / slug(name)
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            frame = fetch_frame(oid)
        except Exception as exc:  # noqa: BLE001 - one dead feed shouldn't sink the rest
            print(f"  {name:8} | (unavailable: {exc})", file=sys.stderr)
            continue
        (out_dir / f"{stamp}.jpg").write_bytes(frame)
        saved += 1
    print(f"{stamp}  saved {saved}/{len(FEEDS)} feeds -> {IMAGES_DIR}")
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect webcam frames for labelling.")
    parser.add_argument("--watch", type=float, metavar="MINUTES",
                        help="keep grabbing every MINUTES minutes")
    parser.add_argument("--rounds", type=int, default=0,
                        help="with --watch, stop after this many rounds (0 = forever)")
    args = parser.parse_args()

    if not args.watch:
        grab_round()
        return 0

    interval = args.watch * 60
    print(f"Collecting every {args.watch:g} min. Press Ctrl+C to stop.\n")
    n = 0
    try:
        while True:
            grab_round()
            n += 1
            if args.rounds and n >= args.rounds:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
