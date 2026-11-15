"""Run an exported model (model.ts and meta.json) over the held-out DEV plans and write detection caches.

    python predict.py --model out/rfdetr-l/export --device cuda            # on the VM, after export
    python predict.py --model out/yolo26m/export --split hold --limit 20

It reads F1_original.png from the public zip (byte-identical to the Stoa PNG) and runs the vendored
bp.tools.symbol_detector.Detector, so the views, the merge and the decode are the same as on the Mac.
It writes <model>/hold_detections.json and hold_detections_mirror.json in the format of
bp.toolbench.cubicasa_detect.detect_plans. Copy them next to the weights in artifacts/cubicasa-detect/<name>/
and `calibrate` uses them instead of running 421 plans twice on the Mac CPU.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CDET_ROOT", str(HERE)))  # views and outputs; outside the synced folder on the VM
sys.path.insert(0, str(HERE / "_vendor"))

import symbol_detector as sd  # noqa: E402


def rows(detections: list[sd.Detection]) -> list[list]:
    return [[d.label, round(d.score, 4), [round(v, 1) for v in d.box]] for d in detections]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Folder with model.ts and meta.json, relative to CDET_ROOT.")
    parser.add_argument("--zip", default="/root/cache/cubicasa5k.zip")
    parser.add_argument("--split", default="hold", help="A list in data/plans.json: hold or train.")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    import torch  # noqa: PLC0415

    model = ROOT / args.model
    plans = json.loads((HERE / "data" / "plans.json").read_text())
    stems = sorted(plans[args.split])[: args.limit or None]
    try:
        detector = sd.Detector(model, device=args.device)
        detector.detect(sd.Image.new("RGB", (800, 600), "white"))
    except Exception as error:  # a traced graph can pin CPU constants; CPU always works
        print(f"device {args.device} failed ({type(error).__name__}: {error}); using cpu", flush=True)
        detector = sd.Detector(model, device="cpu")
        torch.set_num_threads(os.cpu_count() or 4)  # after the Detector, which sets its own thread count
    archive = zipfile.ZipFile(args.zip)
    plain: dict[str, list] = {}
    mirrored: dict[str, list] = {}
    started = time.time()
    for done, stem in enumerate(stems, start=1):
        group, ident = stem.rsplit("-", 1)
        image = sd.load_rgb(io.BytesIO(archive.read(f"cubicasa5k/{group}/{ident}/F1_original.png")))
        with torch.no_grad():
            plain[stem] = rows(detector.detect(image))
            mirrored[stem] = rows(detector.detect(image, mirror=True))
        if done % 50 == 0 or done == len(stems):
            print(f"{done}/{len(stems)} plans, {(time.time() - started) / done:.2f} s per plan", flush=True)
    (model / "hold_detections.json").write_text(json.dumps(plain))
    (model / "hold_detections_mirror.json").write_text(json.dumps(mirrored))
    print(f"wrote {len(plain)} plans to {model}", flush=True)


if __name__ == "__main__":
    main()
