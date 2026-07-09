#!/usr/bin/env python3
"""Train the crowd-density counter on the labelled frames.

Validates honestly: it holds out two whole collection *rounds* (unseen
timestamps) and reports mean absolute count error on them, alongside the
VisDrone detector's error on the same frames so you can see whether the trained
model is actually better.

    ./.venv/bin/python train_counter.py
    ./.venv/bin/python train_counter.py --epochs 200

After training, the script prints a verdict comparing the new val MAE to the
previous run and tells you whether to deploy or roll back — see the tracker
README "Retraining & deploying" section.
"""
import argparse
import json
import random
import shutil
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision.transforms import ColorJitter

from counter_model import (DensityCounter, INPUT_H, INPUT_W, MODEL_OUT,
                           Sample, load_samples, make_density, normalize_image)

SEED = 0
# One JSON line appended per run, so you can plot val MAE vs. labelled frames
# over time and see whether more labelling is still helping.
TRAIN_LOG = MODEL_OUT.with_name("train_log.jsonl")
# The model currently on disk is copied here before a new run overwrites it, so
# a worse retrain can always be rolled back:  mv counter_model.prev.pt counter_model.pt
PREV_MODEL = MODEL_OUT.with_name("counter_model.prev.pt")


def log_run(record: dict) -> None:
    """Append one run's summary to the training log (JSON lines)."""
    with TRAIN_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def previous_run() -> dict | None:
    """The last logged run (i.e. the model currently on disk), or None."""
    if not TRAIN_LOG.exists():
        return None
    lines = [ln for ln in TRAIN_LOG.read_text().splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None


class Frames(Dataset):
    def __init__(self, samples: list[Sample], train: bool):
        self.samples = samples
        self.train = train
        self.jitter = ColorJitter(0.2, 0.2, 0.2, 0.02)
        # Precompute density targets once (cheap, and constant per frame).
        self.dens = [make_density(s.points, s.img_w, s.img_h) for s in samples]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        s = self.samples[i]
        img = Image.open(s.image_path).convert("RGB").resize((INPUT_W, INPUT_H))
        x = torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0).permute(2, 0, 1)
        dens = self.dens[i].copy()
        count = float(len(s.points))
        if self.train:
            if random.random() < 0.5:                 # horizontal flip
                x = torch.flip(x, dims=[2])
                dens = np.ascontiguousarray(dens[:, ::-1])
            x = self.jitter(x)
        x = normalize_image(x)
        return x, torch.from_numpy(dens)[None], torch.tensor(count)


def split_by_round(samples: list[Sample], n_val_rounds: int = 2):
    rounds = sorted({s.round for s in samples})
    if len(rounds) <= n_val_rounds:
        raise SystemExit(f"Need more than {n_val_rounds} rounds; have {len(rounds)}.")
    # Evenly spaced holdout rounds, so val spans different times of day.
    idx = np.linspace(0, len(rounds) - 1, n_val_rounds + 2)[1:-1].round().astype(int)
    val_rounds = {rounds[i] for i in idx}
    train = [s for s in samples if s.round not in val_rounds]
    val = [s for s in samples if s.round in val_rounds]
    return train, val, sorted(val_rounds)


@torch.no_grad()
def val_mae(model, loader):
    model.eval()
    errs = []
    for x, _, count in loader:
        pred = DensityCounter.count_from_density(model(x))
        errs.extend((pred - count).abs().tolist())
    return float(np.mean(errs))


@torch.no_grad()
def detector_baseline(val_samples):
    """VisDrone detector's mean abs count error on the val frames."""
    from detector import detect_people
    errs = []
    for s in val_samples:
        img = Image.open(s.image_path).convert("RGB")
        r = detect_people(img, conf=0.25)
        errs.append(abs(len(r.boxes) - len(s.points)))
    return float(np.mean(errs))


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the crowd-density counter.")
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--patience", type=int, default=30, help="early-stop patience")
    ap.add_argument("--no-baseline", action="store_true",
                    help="skip the (slow) detector baseline comparison")
    args = ap.parse_args()

    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)

    prev = previous_run()   # the model currently on disk — read before we overwrite it
    samples = load_samples()
    if len(samples) < 10:
        raise SystemExit(f"Only {len(samples)} labelled frames; label more first.")
    train_s, val_s, val_rounds = split_by_round(samples)
    print(f"{len(samples)} frames: {len(train_s)} train / {len(val_s)} val")
    print(f"held-out rounds: {', '.join(val_rounds)}\n")

    train_dl = DataLoader(Frames(train_s, True), batch_size=args.batch, shuffle=True)
    val_dl = DataLoader(Frames(val_s, False), batch_size=args.batch)

    model = DensityCounter(pretrained=True)
    opt = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    mse = nn.MSELoss()

    best, best_state, since = float("inf"), None, 0
    for ep in range(1, args.epochs + 1):
        model.train()
        for x, dens, count in train_dl:
            opt.zero_grad()
            pred = model(x)
            loss = mse(pred, dens)
            # small nudge on the number we actually care about
            pcount = DensityCounter.count_from_density(pred)
            loss = loss + 0.05 * (pcount - count).abs().mean()
            loss.backward()
            opt.step()
        mae = val_mae(model, val_dl)
        flag = ""
        if mae < best:
            best, best_state, since, flag = mae, {k: v.clone() for k, v in model.state_dict().items()}, 0, "  <- best"
        else:
            since += 1
        if ep % 10 == 0 or flag:
            print(f"epoch {ep:3d}  val MAE {mae:5.2f}{flag}")
        if since >= args.patience:
            print(f"early stop at epoch {ep} (no improvement in {args.patience})")
            break

    model.load_state_dict(best_state)
    # Back up the model we're about to replace, so a worse run can be rolled back.
    if MODEL_OUT.exists():
        shutil.copy2(MODEL_OUT, PREV_MODEL)
    torch.save({"state_dict": best_state}, MODEL_OUT)
    print(f"\nBest val MAE: {best:.2f} people/frame  ->  saved {MODEL_OUT.name}")

    det = None
    if not args.no_baseline:
        print("\nComparing against the VisDrone detector on the same val frames...")
        det = detector_baseline(val_s)
        print(f"  detector  val MAE: {det:5.2f} people/frame")
        print(f"  our model val MAE: {best:5.2f} people/frame")
        print("  -> " + ("model wins" if best < det else "detector still ahead — needs more data"))

    log_run({
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frames": len(samples),
        "train": len(train_s),
        "val": len(val_s),
        "val_rounds": val_rounds,
        "val_mae": round(best, 3),
        "detector_val_mae": round(det, 3) if det is not None else None,
        "epochs": args.epochs,
    })
    print(f"logged this run to {TRAIN_LOG.name}")

    # --- Verdict + what to do next --------------------------------------
    print("\n" + "=" * 60)
    if prev is None:
        print(f"First logged run. New model val MAE {best:.2f} on {len(samples)} frames.")
        print("Nothing to compare against yet — treat this as the baseline.")
    else:
        delta = best - prev["val_mae"]
        prev_desc = f"previous {prev['val_mae']:.2f} on {prev.get('frames', '?')} frames"
        if delta < -0.05:
            print(f"✅ BETTER: {best:.2f} vs {prev_desc}  (−{abs(delta):.2f}).")
            print("   Keep it. Sanity-check, then deploy:")
            print("     ./beach --no-db                 # counts look reasonable?")
            print("     ./deploy_model.sh <user@pi>     # scp + restart the worker")
        elif delta > 0.05:
            print(f"⚠️  WORSE: {best:.2f} vs {prev_desc}  (+{delta:.2f}).")
            print(f"   The good model was backed up to {PREV_MODEL.name}. To roll back:")
            print(f"     mv {PREV_MODEL.name} {MODEL_OUT.name}")
            print("   (Or keep this one anyway if the val split just got harder.)")
        else:
            print(f"≈ ABOUT THE SAME: {best:.2f} vs {prev_desc}  ({delta:+.2f}).")
            print(f"   Deploy if you like; {PREV_MODEL.name} holds the prior model either way.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
