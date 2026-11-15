#!/bin/bash
# The GPU job: build the views from the public zip once, then run a script (train.py, export.py, train_yolo.py).
#   bash job.sh train.py --epochs 20 --out out/rfdetr-l
#   CDET_STYLES=3 bash job.sh train_yolo.py --out out/yolo26m-styles   (3 synthetic images per Swiss DEV floor)
# `gpu run` syncs this folder with --delete, so views and outputs live in CDET_ROOT, outside it.
set -euo pipefail
cd "$(dirname "$0")"
export CDET_ROOT=/root/cache/cdet
mkdir -p "$CDET_ROOT"
ZIP=/root/cache/cubicasa5k.zip
until [ -f "$ZIP" ] && [ "$(stat -c %s "$ZIP")" = "5469495706" ]; do echo "waiting for $ZIP"; sleep 15; done
if [ ! -f "$CDET_ROOT/data/coco/valid/_annotations.coco.json" ] || [ data/labels.json -nt "$CDET_ROOT/data/coco/valid/_annotations.coco.json" ]; then
  EXTRA=()
  if [ "${CDET_STYLES:-0}" != "0" ]; then
    # Synthetic Swiss floors in many styles (styles.py) and the Stoa PNGs of the DEV floors (pushed to swiss-real).
    apt-get install -y -qq fonts-liberation fonts-dejavu fonts-freefont-ttf fonts-roboto fonts-open-sans \
      fonts-lato fonts-ubuntu fonts-crosextra-carlito fonts-crosextra-caladea fonts-comfortaa >/dev/null 2>&1 || true
    [ -f /root/cache/syn/labels.json ] || python styles.py make --out /root/cache/syn --per "$CDET_STYLES" --workers 20
    EXTRA=(--extra /root/cache/syn --extra /root/work/swiss-real=data/real-labels.json)
  fi
  python prepare.py views --zip "$ZIP" --workers 20 "${EXTRA[@]}"
fi
script="$1"
shift
python "$script" "$@"
