#!/usr/bin/env python3
"""Pre-seed candidate head-points from the VisDrone model.

Runs the detector over each collected frame and drops a point near the top of
each person box (roughly where the head is). These are written as *candidate*
point files so that in the labeller you start from the model's guesses and only
have to add the people it missed (mostly the lying-down sunbathers) and delete
the odd wrong one — much faster than clicking every head from scratch.

Only writes a candidate file where no labels exist yet, so it never clobbers
work you've already done. Run it after collect_frames.py and before labelling.

Usage:
    python preseed_points.py
    python preseed_points.py --conf 0.15     # seed more (lower threshold)
"""
import argparse
import json
import sys

from feeds import HERE
from detector import get_model, person_class_ids

IMAGES_DIR = HERE / "dataset" / "images"
POINTS_DIR = HERE / "dataset" / "points"


def points_from_boxes(boxes) -> list[list[int]]:
    """A head-ish point (top-centre) for each detected person box."""
    pts = []
    for x1, y1, x2, y2 in boxes.xyxy.tolist():
        cx = (x1 + x2) / 2.0
        # 15% down from the top of the box ~ head height
        hy = y1 + 0.15 * (y2 - y1)
        pts.append([round(cx), round(hy)])
    return pts


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed candidate head-points from VisDrone.")
    parser.add_argument("--conf", type=float, default=0.20,
                        help="detection confidence for seeding (default 0.20)")
    parser.add_argument("--imgsz", type=int, default=1280)
    args = parser.parse_args()

    from PIL import Image

    images = sorted(IMAGES_DIR.glob("**/*.jpg"))
    if not images:
        print(f"No images under {IMAGES_DIR}. Run collect_frames.py first.", file=sys.stderr)
        return 1

    model = get_model()  # bundled VisDrone default
    person_ids = person_class_ids(model)
    seeded = skipped = 0
    for img_path in images:
        rel = img_path.relative_to(IMAGES_DIR)
        out = (POINTS_DIR / rel).with_suffix(".json")
        if out.exists():
            skipped += 1
            continue
        image = Image.open(img_path).convert("RGB")
        result = model.predict(image, classes=person_ids, conf=args.conf,
                               imgsz=args.imgsz, iou=0.6, augment=True, verbose=False)[0]
        pts = points_from_boxes(result.boxes)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "points": pts,
            "image_w": image.width,
            "image_h": image.height,
            "candidate": True,   # cleared once you save in the labeller
        }))
        seeded += 1
        print(f"  seeded {len(pts):3d} pts -> {rel}")

    print(f"\nSeeded {seeded} images, skipped {skipped} already-labelled. "
          f"Now run: python label_points.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
