#!/usr/bin/env bash
# Push the freshly-trained counter to the Pi and restart the worker.
#
# Run this FROM your dev box AFTER train_counter.py, once you're happy with the
# new model's val MAE (the training run prints a verdict; see the tracker README
# "Retraining & deploying" section). The model file is git-ignored, so this scp
# is the only way it reaches the Pi.
#
#   ./deploy_model.sh pi@raspberrypi.local     # explicit host
#   KP_PI_HOST=pi@raspberrypi.local ./deploy_model.sh
#   KP_PI_DIR=/srv/kingstonpier ./deploy_model.sh pi@host   # non-default repo path
#
# Assumes the worker unit is installed on the Pi (deploy/install.sh worker).

set -euo pipefail
cd "$(dirname "$0")"

HOST="${1:-${KP_PI_HOST:-}}"
PI_DIR="${KP_PI_DIR:-~/kingstonpier}"   # ~ is expanded by the remote shell
MODEL="counter_model.pt"

if [[ -z "$HOST" ]]; then
  echo "Usage: ./deploy_model.sh <user@pi-host>   (or set KP_PI_HOST)" >&2
  exit 2
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERROR: $MODEL not found here — run train_counter.py first." >&2
  exit 1
fi

echo "model : $(du -h "$MODEL" | cut -f1)  $MODEL"
echo "target: $HOST:$PI_DIR/tracker/"
scp "$MODEL" "$HOST:$PI_DIR/tracker/$MODEL"

echo "Restarting kingstonpier-cv-worker on $HOST ..."
ssh "$HOST" "sudo systemctl restart kingstonpier-cv-worker && sleep 2 && systemctl is-active kingstonpier-cv-worker"

echo
echo "Deployed. Watch a pass:  ssh $HOST journalctl -u kingstonpier-cv-worker -f"
echo "Verify public       :  curl -s https://api.kingstonpier.ca/now"
