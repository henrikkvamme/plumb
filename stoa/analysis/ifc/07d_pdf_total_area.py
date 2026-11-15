# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.26.5", "shapely"]
# ///
"""Probe: does the sum of all light-blue room polygons on a sheet reproduce the
"total net floor area of all rooms on <storey>" answers? Uses the helpers of 07_pdf_room_area.py.
Also wall length from the sheet is NOT probed (walls join, so per-wall axis length is not on the sheet).
Writes out/pdf_total_area.json.
"""
import importlib.util
import json
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p07", HERE / "07_pdf_room_area.py")
p07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p07)


def main():
    rows = [json.loads(l) for l in open(HERE / "out" / "probe_rows.jsonl")]
    res = []
    for r in rows:
        if r["family"] != "area_total_storey" or not r["path"].endswith(".pdf"):
            continue
        page = pymupdf.open(p07.MD / r["path"])[0]
        mpp = p07.scale_from_bar(page)
        polys = []
        for d in page.get_drawings():
            if p07.is_blue(d.get("fill")):
                g = p07.path_polys(d)
                if g is not None and g.area > 0.5:
                    polys.append(g)
        s = sum(g.area for g in polys) * mpp**2
        res.append({"pdf": r["path"], "ref": r["ref"], "sum_polygons": round(s, 2), "ok": abs(s - r["ref"]) <= 0.02 * r["ref"]})
    summ = {"n": len(res), "ok": sum(x["ok"] for x in res), "misses": [x for x in res if not x["ok"]][:10]}
    json.dump({"summary": summ, "rows": res}, open(HERE / "out" / "pdf_total_area.json", "w"), indent=1)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
