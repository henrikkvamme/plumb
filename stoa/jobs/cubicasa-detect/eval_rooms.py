"""End to end on the Stoa PNGs of Swiss floors: rooms from `raster_rooms.read_plan`, boxes from the detector,
`raster_openings.room_openings` for the count of each room, against the true count of the room with that number.

    uv run python jobs/cubicasa-detect/eval_rooms.py <model dir> --partition dev --limit 40 [--reach 0.1]
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bp.tools import ocr, raster_openings, raster_rooms
from bp.tools.symbol_detector import Detector, load_rgb

HERE = Path(__file__).resolve().parent
SWISS = HERE.parents[1] / "data" / "junction-dataset" / "data" / "swiss_dwellings"


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--partition", default="dev")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--reach", type=float, default=raster_openings.REACH_M)
    args = parser.parse_args()
    detector = Detector.get(Path(args.model))
    calib = detector.meta.get("calibration", {})
    real = json.loads((HERE / "data" / "real-labels.json").read_text())
    stems = [k for k, v in sorted(real.items()) if v["partition"] == args.partition][: args.limit]

    def one(stem: str) -> list[dict]:
        path = SWISS / f"{stem}.png"
        rgb = ocr.to_rgb(path)
        plan = raster_rooms.read_plan(rgb, ocr.read_lines(rgb))
        found = detector.detect(load_rgb(path))
        if plan.scale is None:
            return []
        truth = {r["number"]: r for r in real[stem]["rooms"]}
        rooms = [r for r in plan.rooms if len(r.polygon) >= 3]  # noqa: PLR2004
        shapes = [raster_openings.shape_of(r.polygon) for r in rooms]
        rows = [{"number": r.number, "known": r.number in truth} for r in rooms]
        for cls, key, ids in (("door", "doors", "door_ids"), ("window", "windows", "window_ids")):
            c = calib.get(key, {})
            got = raster_openings.room_openings(shapes, found, cls, float(c.get("threshold", 0.5)),
                                                float(c.get("band", 0.0)), plan.scale.ppm, args.reach)  # fmt: skip
            for row, g in zip(rows, got, strict=True):
                if row["known"]:
                    row[cls] = (g.count, g.sure, len(truth[row["number"]][ids]))
        rows.append({"missed": len(truth) - sum(r["known"] for r in rows), "of": len(truth)})
        return rows

    def safe(stem: str) -> list[dict]:
        try:
            return one(stem)
        except BaseException as exc:  # noqa: BLE001 - report the sheet, keep the run
            print(stem, type(exc).__name__, repr(exc)[:300], flush=True)
            traceback.print_exc()
            return []

    with ThreadPoolExecutor(1) as pool:
        rows = [r for part in pool.map(safe, stems) for r in part]
    missed = sum(r.get("missed", 0) for r in rows)
    total = sum(r.get("of", 0) for r in rows)
    print(json.dumps({"sheets": len(stems), "true_rooms": total, "rooms_not_read": missed}), flush=True)
    for cls in ("door", "window"):
        got = [r[cls] for r in rows if cls in r]
        sure = [g for g in got if g[1]]
        print(cls, json.dumps({
            "rooms": len(got), "exact": round(sum(g[0] == g[2] for g in got) / len(got), 3),
            "sure_share": round(len(sure) / len(got), 3),
            "sure_exact": round(sum(g[0] == g[2] for g in sure) / max(1, len(sure)), 3),
            "has_any_right": round(sum((g[0] > 0) == (g[2] > 0) for g in got) / len(got), 3),
            "sure_has_any_right": round(sum((g[0] > 0) == (g[2] > 0) for g in sure) / max(1, len(sure)), 3),
        }), flush=True)  # fmt: skip


if __name__ == "__main__":
    main()
