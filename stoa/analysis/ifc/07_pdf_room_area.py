# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.26.5", "shapely"]
# ///
"""Probe: can the room-area questions on ifc_models PDF sheets be answered from the sheet alone?

The sheets print no areas. They draw each IfcSpace as a light-blue filled vector polygon, with the
room name and number as text. This probe:
  1. finds the room label (name line above number line, or a name-only line),
  2. takes the smallest light-blue filled polygon that contains the label centre,
  3. converts its area from PDF points to m2 with the scale bar (0 .. "5 m") and, separately, the printed 1:N,
  4. compares with Stoa's reference (2% rule).
Also counts the light-blue polygons per sheet against the reference "rooms on the floor plan" counts.
Writes out/pdf_room_area.json.
"""
import collections
import json
import re
from pathlib import Path

import pymupdf
from shapely.geometry import Point, Polygon
from shapely.validation import make_valid

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
MD = DS / "data" / "ifc_models"
OUT = HERE / "out"
QUOTE = re.compile(r"'([^']*)'|„([^“”]*)[“”]|«([^»]*)»")
BLUE = (0.89, 0.93, 0.97)
PT_M = 0.0254 / 72  # one PDF point in metres on paper


def is_blue(c):
    return c is not None and len(c) == 3 and all(abs(a - b) < 0.03 for a, b in zip(c, BLUE))


def path_polys(d):
    """Polygons from a drawing's items; a new sub-path starts when a segment does not continue the last point."""
    polys, cur = [], []
    for it in d["items"]:
        if it[0] == "l":
            p1, p2 = it[1], it[2]
            if cur and (abs(cur[-1][0] - p1.x) > 0.01 or abs(cur[-1][1] - p1.y) > 0.01):
                polys.append(cur)
                cur = []
            if not cur:
                cur.append((p1.x, p1.y))
            cur.append((p2.x, p2.y))
        elif it[0] == "re":
            r = it[1]
            polys.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif it[0] == "qu":
            q = it[1]
            polys.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
        elif it[0] == "c":
            p1, p4 = it[1], it[4]
            if not cur:
                cur.append((p1.x, p1.y))
            cur.append((p4.x, p4.y))
    if cur:
        polys.append(cur)
    out = []
    for p in polys:
        if len(p) >= 3:
            g = make_valid(Polygon(p))
            if g.area > 0:
                out.append(g)
    if not out:
        return None
    # even-odd: a polygon inside another polygon of the same path is a hole
    out.sort(key=lambda g: -g.area)
    shape = out[0]
    for g in out[1:]:
        shape = shape.difference(g) if shape.contains(g) else shape.union(g)
    return shape


def scale_from_bar(page):
    """Metres per PDF point from the scale bar: the '0' and '5 m' labels below the bar."""
    words = page.get_text("words")
    fives = [w for w in words if w[4] == "m"]
    zeros = [w for w in words if w[4] == "0"]
    best = None
    for m in fives:
        five = [w for w in words if w[4] == "5" and abs(w[1] - m[1]) < 2 and 0 < m[0] - w[2] < 6]
        if not five:
            continue
        x5 = (five[0][0] + m[2]) / 2
        for z in zeros:
            if abs(z[1] - m[1]) < 2 and z[0] < five[0][0]:
                x0 = (z[0] + z[2]) / 2
                best = 5.0 / (x5 - x0)
    return best


def main():
    qs = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_models/' in l and l.find(".pdf") > 0]
    by_pdf = collections.defaultdict(list)
    for r in qs:
        by_pdf[r["path"].split("/")[-1]].append(r)
    res_rows = []
    sheet_info = {}
    for pdf, rs in sorted(by_pdf.items()):
        page = pymupdf.open(MD / pdf)[0]
        txt = page.get_text()
        m = re.search(r"1\s*:\s*(\d+)", txt)
        n_scale = int(m.group(1)) if m else None
        mpp_bar = scale_from_bar(page)
        mpp_txt = PT_M * n_scale if n_scale else None
        blues = []
        for d in page.get_drawings():
            if is_blue(d.get("fill")):
                g = path_polys(d)
                if g is not None and g.area > 0.5:
                    blues.append(g)
        lines = []
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                x0, y0, x1, y1 = l["bbox"]
                lines.append((t, (x0 + x1) / 2, (y0 + y1) / 2, y1 - y0))
        sheet_info[pdf] = {"n_blue": len(blues), "scale_txt": n_scale, "m_per_pt_bar": mpp_bar, "m_per_pt_txt": mpp_txt}
        for r in rs:
            ql = r["question"].lower()
            if r["type"] == "count" and any(w in ql for w in ["room", "räume", "ruimte", "locales", " rum ", "ruumi", "pomieszcze"]) and not any(w in ql for w in ["model", "mudel"]):
                res_rows.append({"pdf": pdf, "kind": "room_count", "ref": r["answer"], "n_blue": len(blues)})
            if r["type"] != "area":
                continue
            qq = [next(x for x in mm if x) for mm in QUOTE.findall(r["question"])]
            if len(qq) < 2:
                continue
            room = qq[0]
            mm = re.match(r"(.*) \((.*)\)$", room)
            name, num = (mm.group(1), mm.group(2)) if mm else (room, None)
            cands = []
            if num:
                for t, x, y, h in lines:
                    if t == num:
                        above = [l for l in lines if l[0] == name and abs(l[1] - x) < 40 and 0 < y - l[2] < 2.5 * h]
                        cands.append((x, y - h / 2 if above else y, bool(above)))
                cands.sort(key=lambda c: not c[2])
            else:
                cands = [(x, y, True) for t, x, y, h in lines if t == name]
            rec = {"pdf": pdf, "kind": "room_area", "room": room, "ref": r["answer"], "n_label": len(cands)}
            if cands:
                x, y, _ = cands[0]
                pt = Point(x, y)
                inside = [g for g in blues if g.contains(pt)]
                if inside:
                    g = min(inside, key=lambda g: g.area)
                    rec["area_bar"] = g.area * mpp_bar**2 if mpp_bar else None
                    rec["area_txt"] = g.area * mpp_txt**2 if mpp_txt else None
            for k in ("area_bar", "area_txt"):
                v = rec.get(k)
                rec["ok_" + k] = v is not None and abs(v - r["answer"]) <= 0.02 * r["answer"]
            res_rows.append(rec)
    ra = [r for r in res_rows if r["kind"] == "room_area"]
    rc = [r for r in res_rows if r["kind"] == "room_count"]
    summ = {
        "room_area_n": len(ra),
        "label_found": sum(1 for r in ra if r["n_label"]),
        "label_ambiguous": sum(1 for r in ra if r["n_label"] > 1),
        "polygon_found": sum(1 for r in ra if r.get("area_bar") is not None),
        "ok_bar": sum(r["ok_area_bar"] for r in ra), "ok_txt": sum(r["ok_area_txt"] for r in ra),
        "ok_bar_pct": round(100 * sum(r["ok_area_bar"] for r in ra) / len(ra), 1),
        "per_pdf_ok": {p: [sum(1 for r in ra if r["pdf"] == p and r["ok_area_bar"]), sum(1 for r in ra if r["pdf"] == p)] for p in sorted({r["pdf"] for r in ra})},
        "room_count_n": len(rc), "room_count_eq_blue": sum(1 for r in rc if r["ref"] == r["n_blue"]),
        "room_count_examples": [r for r in rc if r["ref"] != r["n_blue"]][:12],
        "bar_vs_txt_ratio": sorted({round(v["m_per_pt_bar"] / v["m_per_pt_txt"], 4) for v in sheet_info.values() if v["m_per_pt_bar"] and v["m_per_pt_txt"]}),
        "fail_examples": [r for r in ra if not r["ok_area_bar"]][:15],
    }
    json.dump({"summary": summ, "sheets": sheet_info, "rows": res_rows}, open(OUT / "pdf_room_area.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summ.items() if k not in ("per_pdf_ok", "fail_examples", "room_count_examples")}, indent=0))


if __name__ == "__main__":
    main()
