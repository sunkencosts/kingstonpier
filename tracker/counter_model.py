#!/usr/bin/env python3
"""Shared pieces for the crowd-density counter: data, density maps, model.

The counter regresses a *density map* from a frame — a blurred heat image where
each labelled person contributes a little blob of total mass 1, so the sum over
the whole map is the person count. Density regression uses every labelled point
as supervision, which is why it can learn from only a few dozen frames where
plain "predict one number" regression would just overfit.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

HERE = Path(__file__).resolve().parent
IMAGES_DIR = HERE / "dataset" / "images"
POINTS_DIR = HERE / "dataset" / "points"
MODEL_OUT = HERE / "counter_model.pt"

# Network input size (keeps the ~16:9 webcam aspect) and the stride of the
# density map it predicts. 512x288 at stride 8 -> a 64x36 density map.
INPUT_W, INPUT_H = 512, 288
STRIDE = 8
DENS_W, DENS_H = INPUT_W // STRIDE, INPUT_H // STRIDE  # 64 x 36

SIGMA = 1.5          # Gaussian spread of each point, in density-map pixels
DENS_SCALE = 100.0   # scale density up so MSE gradients aren't vanishingly small

# ImageNet stats for the pretrained backbone.
_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


@dataclass
class Sample:
    image_path: Path
    points: list          # [[x, y], ...] in original-image pixels
    img_w: int
    img_h: int
    feed: str             # e.g. "pier_1"
    round: str            # timestamp stem, e.g. "2026-07-07T15-20-10"


def load_samples() -> list[Sample]:
    """All confirmed-labelled frames (skips model-seeded candidates)."""
    out = []
    for img in sorted(IMAGES_DIR.glob("**/*.jpg")):
        rel = img.relative_to(IMAGES_DIR)
        pf = (POINTS_DIR / rel).with_suffix(".json")
        if not pf.exists():
            continue
        d = json.loads(pf.read_text())
        if d.get("candidate"):      # not yet confirmed by a human
            continue
        out.append(Sample(
            image_path=img, points=d.get("points", []),
            img_w=d.get("image_w") or 640, img_h=d.get("image_h") or 360,
            feed=rel.parent.name, round=img.stem))
    return out


def make_density(points, img_w, img_h) -> np.ndarray:
    """Build a (DENS_H, DENS_W) density map summing to len(points)*DENS_SCALE."""
    dens = np.zeros((DENS_H, DENS_W), dtype=np.float32)
    sx, sy = DENS_W / img_w, DENS_H / img_h
    rad = int(math.ceil(3 * SIGMA))
    for x, y in points:
        cx, cy = x * sx, y * sy
        x0, x1 = max(0, int(cx) - rad), min(DENS_W, int(cx) + rad + 1)
        y0, y1 = max(0, int(cy) - rad), min(DENS_H, int(cy) + rad + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        g = np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * SIGMA ** 2))
        s = g.sum()
        if s > 0:
            dens[y0:y1, x0:x1] += (g / s).astype(np.float32)  # each point -> mass 1
    return dens * DENS_SCALE


def normalize_image(chw: torch.Tensor) -> torch.Tensor:
    """CHW float image in [0,1] -> ImageNet-normalised."""
    return (chw - _MEAN) / _STD


class DensityCounter(nn.Module):
    """Frozen MobileNetV3-small encoder + a small trained density decoder."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        from torchvision.models import (mobilenet_v3_small,
                                         MobileNet_V3_Small_Weights)
        weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
        self.encoder = mobilenet_v3_small(weights=weights).features  # stride 32, 576ch
        for p in self.encoder.parameters():   # freeze: only the head learns
            p.requires_grad = False

        def block(cin, cout):
            return nn.Sequential(
                nn.Conv2d(cin, cout, 3, padding=1), nn.ReLU(inplace=True),
                nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False))

        self.decoder = nn.Sequential(
            block(576, 128),   # stride 32 -> 16
            block(128, 64),    # 16 -> 8
            nn.Conv2d(64, 32, 3, padding=1), nn.ReLU(inplace=True),
            # Softplus (not ReLU) on the output: density stays >= 0 but keeps a
            # non-zero gradient at 0, so the map can't get trapped at all-zeros.
            nn.Conv2d(32, 1, 1), nn.Softplus())

    def forward(self, x):
        feat = self.encoder(x)
        dens = self.decoder(feat)            # (N,1,h,w) at ~stride 8
        return dens

    @staticmethod
    def count_from_density(dens: torch.Tensor) -> torch.Tensor:
        """Sum a predicted density map back to a person count."""
        return dens.sum(dim=(1, 2, 3)) / DENS_SCALE


# --- Inference (used by the tracker) --------------------------------------
_COUNTER = None


def load_counter():
    """Load the trained density counter once and reuse it."""
    global _COUNTER
    if _COUNTER is None:
        if not MODEL_OUT.exists():
            raise SystemExit(
                f"No trained model at {MODEL_OUT.name}. Run train_counter.py first.")
        m = DensityCounter(pretrained=False)
        m.load_state_dict(torch.load(MODEL_OUT, map_location="cpu")["state_dict"])
        m.eval()
        _COUNTER = m
    return _COUNTER


@torch.no_grad()
def count_image(jpeg_or_pil) -> int:
    """People count for one frame (JPEG bytes or a PIL image)."""
    import io
    from PIL import Image
    img = (jpeg_or_pil if isinstance(jpeg_or_pil, Image.Image)
           else Image.open(io.BytesIO(jpeg_or_pil))).convert("RGB")
    x = torch.from_numpy(
        np.asarray(img.resize((INPUT_W, INPUT_H)), dtype=np.float32) / 255.0
    ).permute(2, 0, 1)
    x = normalize_image(x)[None]
    dens = load_counter()(x)
    return round(float(DensityCounter.count_from_density(dens)[0]))
