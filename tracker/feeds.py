#!/usr/bin/env python3
"""The Breakwater Park webcam feeds — shared by the tracker and the tools.

Kept dependency-light (just `requests`) so the labelling web tool and the frame
collector can import it without pulling in torch or ultralytics.

The City of Kingston's Breakwater Park "webcam" is actually a group of five
separate cameras — Pier 1 through Pier 5 — behind a single Ozolio player. The
player's session API enumerates the five channels, each with its own camera
object id (CID_...); every one has a plain snapshot endpoint that returns a
fresh ~640x360 JPEG:

    https://relay.ozolio.com/pub.api?cmd=snap&oid=<CID>
"""
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent

CAMERA_NAME = "Breakwater Park, Kingston"
SNAP_URL = "https://relay.ozolio.com/pub.api?cmd=snap&oid={oid}"

# (feed name, Ozolio camera object id)
FEEDS = [
    ("Pier 1", "CID_ZISK000007EB"),
    ("Pier 2", "CID_SNNG000007DC"),
    ("Pier 3", "CID_JPAO000007F0"),
    ("Pier 4", "CID_YBRA000007D2"),
    ("Pier 5", "CID_IUUE000007B9"),
]


def fetch_frame(oid: str, timeout: int = 20) -> bytes:
    """Download a fresh JPEG snapshot from one webcam feed."""
    resp = requests.get(SNAP_URL.format(oid=oid),
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    resp.raise_for_status()
    if not resp.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(
            f"Webcam did not return an image (got {resp.headers.get('content-type')}). "
            "The feed may be temporarily down."
        )
    return resp.content


def slug(name: str) -> str:
    """'Pier 1' -> 'pier_1', for filenames and DB column names."""
    return name.lower().replace(" ", "_")
