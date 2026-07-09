#!/usr/bin/env python3
"""Breakwater Park crowd tracker — the sampling worker.

Grabs a fresh snapshot from each of the five Breakwater Park feeds, counts the
people with the trained density model (train_counter.py), and appends one
integer-count row to the SQLite `readings` table that the kingstonpier API
serves. Counts only — no images are stored (the privacy stance).

Usage:
    python crowd_tracker.py                 # count every feed once, write a row
    python crowd_tracker.py --watch 3       # keep sampling every 3 minutes
    python crowd_tracker.py --no-db         # print only, don't write a row
    python crowd_tracker.py --image FILE    # count one saved frame (spot check)

The counter it uses is trained on your own labelled frames; see the README for
the collect -> label -> train loop. Point the DB at the API's store with
KP_DB_PATH (see db.py).
"""
import argparse
import sys
import time

from feeds import CAMERA_NAME, FEEDS, fetch_frame, slug
from counter_model import count_image
from db import append_reading, db_path


def do_one(write: bool) -> int:
    """Count every feed, print a breakdown, append a reading; return the total."""
    counts: dict[str, int] = {}
    for name, oid in FEEDS:
        try:
            c = count_image(fetch_frame(oid))
        except Exception as exc:  # noqa: BLE001 - one dead feed shouldn't sink the rest
            print(f"  {name:8} |  (unavailable: {exc})", file=sys.stderr)
            continue
        if c is None:            # too dark to count — record no reading, not a guess
            print(f"  {name:8} |  (dark, skipped)")
            continue
        counts[name] = c
        print(f"  {name:8} |  {c:3d} people")

    total = sum(counts.values())
    partial = "" if len(counts) == len(FEEDS) else f" (from {len(counts)}/{len(FEEDS)} feeds)"
    print(f"  {'TOTAL':8} |  {total:3d} people{partial}")
    if write and counts:
        append_reading(counts)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count people at Breakwater Park and log to the readings DB.")
    parser.add_argument("--watch", type=float, metavar="MINUTES",
                        help="keep sampling every MINUTES minutes")
    parser.add_argument("--no-db", action="store_true",
                        help="print only; don't append a row to the readings DB")
    parser.add_argument("--image", help="count one saved image instead of the live feeds")
    args = parser.parse_args()

    if args.image:
        c = count_image(open(args.image, "rb").read())
        print(f"{args.image}: " + ("too dark to count" if c is None else f"{c} people"))
        return 0

    write = not args.no_db
    print(f"Camera: {CAMERA_NAME}" + ("" if not write else f"  ->  {db_path()}"))

    if not args.watch:
        try:
            do_one(write)
        except Exception as exc:  # noqa: BLE001 - friendly top-level message
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    interval = args.watch * 60
    print(f"Sampling every {args.watch:g} min. Press Ctrl+C to stop.\n")
    try:
        while True:
            from db import utc_now_iso
            print(utc_now_iso())
            try:
                do_one(write)
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                print(f"  (skipped: {exc})", file=sys.stderr)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
