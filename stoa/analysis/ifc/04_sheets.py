# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.26.5"]
# ///
"""Survey of the 107 rendered PDF sheets in ifc_models.

Per sheet: page size, number of vector paths, number of text spans, the scale text, whether
any number followed by m2/m² is printed, whether room names from the questions appear as text.
Also renders a PNG preview of selected sheets to out/sheets/ for viewing.
Writes out/sheets.json.
"""
import collections
import json
import re
import sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
OUT = HERE / "out"
(OUT / "sheets").mkdir(parents=True, exist_ok=True)

QUOTE = re.compile(r"'([^']*)'|„([^“]*)“|«([^»]*)»")


def main():
    qs = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_models/' in l]
    names_by_pdf = collections.defaultdict(set)
    for r in qs:
        if r["path"].endswith(".pdf") and r["type"] == "area":
            m = QUOTE.findall(r["question"])
            if m and len([x for x in m[0] if x]) and len(m) >= 2:
                room = next(x for x in m[0] if x)
                names_by_pdf[r["path"].split("/")[-1]].add(room)
    res = []
    for p in sorted((DS / "data" / "ifc_models").glob("*.pdf")):
        d = pymupdf.open(p)
        pg = d[0]
        text = pg.get_text()
        words = pg.get_text("words")
        draws = pg.get_drawings()
        scale = re.findall(r"(?:1\s*:\s*\d+)", text)
        area_txt = re.findall(r"\d+[.,]\d+\s*(?:m2|m²|qm)", text)
        dims = re.findall(r"\b\d{3,5}\b", text)
        rooms = names_by_pdf.get(p.name, set())
        # room 'Name (Number)': the sheet prints Name and Number as separate lines
        found = 0
        for rn in rooms:
            m = re.match(r"(.*) \((.*)\)$", rn)
            nm, num = (m.group(1), m.group(2)) if m else (rn, "")
            if num and num in text:
                found += 1
        kind = p.stem.split("_")[-1].split("-")[0]
        res.append({
            "pdf": p.name, "kind": kind, "pages": len(d), "w_pt": round(pg.rect.width), "h_pt": round(pg.rect.height),
            "n_paths": len(draws), "n_words": len(words), "n_images": len(pg.get_images()),
            "scale": scale[:3], "area_text": area_txt[:5], "n_area_text": len(area_txt),
            "n_rooms_in_questions": len(rooms), "room_numbers_printed": found,
            "has_questions": any(r["path"].endswith(p.name) for r in qs),
            "title": [l for l in text.splitlines() if "—" in l][:1],
        })
    json.dump(res, open(OUT / "sheets.json", "w"), indent=1, ensure_ascii=False)
    kinds = collections.Counter(r["kind"] for r in res)
    withq = collections.Counter(r["kind"] for r in res if r["has_questions"])
    scales = collections.Counter(tuple(r["scale"][:1]) for r in res)
    print("kinds", dict(kinds), "with questions", dict(withq))
    print("scales", dict(scales))
    print("sheets with printed area text", sum(1 for r in res if r["n_area_text"]))
    print("raster images on sheets", sum(r["n_images"] for r in res))
    tot_rooms = sum(r["n_rooms_in_questions"] for r in res)
    tot_found = sum(r["room_numbers_printed"] for r in res)
    print("room ids printed / asked", tot_found, tot_rooms)
    for name in sys.argv[1:]:
        pg = pymupdf.open(DS / "data" / "ifc_models" / name)[0]
        pix = pg.get_pixmap(dpi=110)
        pix.save(OUT / "sheets" / (Path(name).stem + ".png"))


if __name__ == "__main__":
    main()
