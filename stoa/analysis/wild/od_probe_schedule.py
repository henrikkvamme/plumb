# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""Probe: can a ~40-line text-layer table parser reproduce the opening_design reference answers
on A-801 (Sports Complex)? Also runs the same parser on the archived 2015-08-14 permit version of
A-801 and prints which answers change between revisions.

Writes analysis/wild/out/od_probe_schedule.json. Run: uv run stoa/analysis/wild/od_probe_schedule.py
"""
import json, re, collections
from pathlib import Path
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[2] / "data/junction-dataset"
OD = ROOT / "data/opening_design/Sports_Complex"
CUR = OD / "Sheets - Current Set/A-801 - Door and Finish Schedules & Wall Types.pdf"
OLD = OD / "Transfer/_Archive/20150814 - Issued for Permit/XSC - A-801 - Door and Finish Schedules & Wall Types.pdf"
OUT = Path(__file__).resolve().parent / "out"

DOOR = re.compile(r"^\d{3}\.[A-Z]\d?$")
ROOM_AREA = re.compile(r"^\d+$")


def rows(pdf):
    pg = fitz.open(pdf)[0]
    words = pg.get_text("words")
    m = pg.rotation_matrix  # sheets are stored rotated 90 degrees; map words to the visible frame
    W = pg.rect.width
    by = collections.defaultdict(list)
    for x0, y0, x1, y1, w, *_ in words:
        r = fitz.Rect(x0, y0, x1, y1) * m
        by[round((r.y0 + r.y1) / 2 / 3.0)].append((r.x0, w))
    out = []
    for k in sorted(by):
        out.append([w for _, w in sorted(by[k])] + [min(x for x, _ in by[k]) / W])
    return out


def door_table(rs):
    doors = []
    for r in rs:
        toks, xfrac = r[:-1], r[-1]
        if toks and DOOR.match(toks[0]) and xfrac < 0.25:
            doors.append(toks)
    return doors


def finish_table(rs):
    rooms = []
    for r in rs:
        toks = r[:-1]
        # "108 SF 100 X. VEST. F1 B1 ..." or "Redundant Room 123"
        if len(toks) >= 3 and ROOM_AREA.match(toks[0]) and toks[1] == "SF" and ROOM_AREA.match(toks[2]):
            rooms.append(toks)
    return rooms


def answers(pdf):
    rs = rows(pdf)
    d = door_table(rs)
    f = finish_table(rs)
    types = collections.Counter()
    for t in d:
        for tok in t:
            if re.fullmatch(r"[ABC][123]", tok):
                types[tok] += 1
                break
    a = {
        "n_doors": len(d),
        "type_counts": dict(types),
        "doors_room_118": sum(1 for t in d if t[0].startswith("118.")),
        "doors_room_128": sum(1 for t in d if t[0].startswith("128.")),
        "n_rooms_with_area": len(f),
        "area_128": next((int(t[0]) for t in f if t[2] == "128"), None),
        "area_118": next((int(t[0]) for t in f if t[2] == "118"), None),
        "area_122": next((int(t[0]) for t in f if t[2] == "122"), None),
        "area_121": next((int(t[0]) for t in f if t[2] == "121"), None),
        "total_area": sum(int(t[0]) for t in f),
        "office_area": sum(int(t[0]) for t in f if t[3] == "OFFICE"),
        "restroom_area": sum(int(t[0]) for t in f if t[3] == "RESTROOM"),
        "door_rows": [" ".join(t) for t in d],
    }
    return a


def main():
    cur, old = answers(CUR), answers(OLD)
    ref = {"n_doors": 38, "A1": 14, "A2": 1, "B1": 9, "B2": 10, "B3": 1, "C1": 1,
           "doors_room_118": 5, "doors_room_128": 5, "area_128": 29690, "area_118": 5183,
           "area_122": 3814, "area_121": 2470, "total_area": 49560, "office_area": 816, "restroom_area": 193}
    got = {**{k: cur[k] for k in ref if k in cur}, **{k: cur["type_counts"].get(k, 0) for k in ["A1", "A2", "B1", "B2", "B3", "C1"]}}
    gold = {**{k: old[k] for k in ref if k in old}, **{k: old["type_counts"].get(k, 0) for k in ["A1", "A2", "B1", "B2", "B3", "C1"]}}
    agree = {k: (got.get(k), ref[k], got.get(k) == ref[k]) for k in ref}
    res = {
        "agreement_current": sum(v[2] for v in agree.values()), "n_checked": len(ref),
        "detail_current": agree,
        "archive_2015_08_14_values": gold,
        "changed_between_revisions": {k: (gold.get(k), got.get(k)) for k in ref if gold.get(k) != got.get(k)},
        "n_rooms_with_area_current": cur["n_rooms_with_area"],
        "door_rows_current": cur["door_rows"],
        "door_rows_archive": old["door_rows"],
    }
    json.dump(res, open(OUT / "od_probe_schedule.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ["agreement_current", "n_checked", "changed_between_revisions", "n_rooms_with_area_current"]}))
    print({k: v for k, v in agree.items() if not v[2]})


if __name__ == "__main__":
    main()
