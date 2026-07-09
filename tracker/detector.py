#!/usr/bin/env python3
"""YOLO person detector — used only by the labelling pipeline, not the tracker.

Two jobs:
  * preseed_points.py — turn detections into candidate head-points to label from
  * train_counter.py  — a baseline to compare the trained counter against

The runtime tracker counts with the trained density model (counter_model.py)
and never imports this. The default weights are a VisDrone-trained yolov8x
(good on small/aerial people); download once with:

    curl -L -o yolov8x-visdrone.pt \\
      https://huggingface.co/mshamrai/yolov8x-visdrone/resolve/main/best.pt
"""
from feeds import HERE

# COCO says "person"; VisDrone splits people into "pedestrian" + "people" — we
# want all of them. Matching by name means either weights file just works.
PERSON_NAMES = {"person", "pedestrian", "people"}
MODEL_FILE = HERE / "yolov8x-visdrone.pt"
MODEL_DOWNLOAD_HINT = (
    "curl -L -o yolov8x-visdrone.pt "
    "https://huggingface.co/mshamrai/yolov8x-visdrone/resolve/main/best.pt")

_MODEL = None


def get_model(model_spec: str | None = None):
    """Load the YOLO model once and reuse it."""
    global _MODEL
    if _MODEL is None:
        spec = model_spec
        if spec is None:
            if not MODEL_FILE.exists():
                raise RuntimeError(
                    f"Model file not found: {MODEL_FILE.name}. Download it once with:\n"
                    f"    {MODEL_DOWNLOAD_HINT}")
            spec = str(MODEL_FILE)
        from ultralytics import YOLO  # lazy: keeps --help fast, import optional
        _MODEL = YOLO(spec)
    return _MODEL


def person_class_ids(model) -> list[int]:
    """Class ids in this model that represent a person (see PERSON_NAMES)."""
    return [i for i, name in model.names.items() if str(name).lower() in PERSON_NAMES]


def detect_people(image, conf: float = 0.20, imgsz: int = 1280, augment: bool = True):
    """Run person detection on a PIL image; return the boxes result."""
    model = get_model()
    return model.predict(image, classes=person_class_ids(model), conf=conf,
                         iou=0.6, imgsz=imgsz, augment=augment, verbose=False)[0]
