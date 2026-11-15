# /// script
# requires-python = ">=3.11"
# dependencies = ["ifcopenshell==0.9.0.post1"]
# ///
"""Label-noise check.

Part A (ifc_models): a seeded sample of 30 questions, stratified by family. For each row it shows the
reference, the Qto value, the IFC geometry value, the PDF polygon area (from 07) and semantic flags from 08
(duplicate or overlapping spaces, roof/gross spaces), and gives a verdict:
  consistent      every independent reading agrees within 2% (or exactly for counts)
  convention      the reference follows one reading and another reading differs by more than 2%
  contradicted    no reading agrees
Part B (ifc_bench): every reference that states "Total <thing>: N" for doors, windows, walls, slabs, stairs,
spaces, columns, beams, members is compared with the IfcOpenShell by_type count of that class.
Writes out/label_check.json.
"""
import collections
import json
import random
import re
from pathlib import Path

import ifcopenshell

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
OUT = HERE / "out"


def part_a():
    rows = [json.loads(l) for l in open(OUT / "probe_rows.jsonl")]
    pdf = {(r["pdf"], r["room"]): r for r in json.load(open(OUT / "pdf_room_area.json"))["rows"] if r["kind"] == "room_area"}
    sem = json.load(open(OUT / "space_semantics.json"))
    random.seed(30)
    fams = collections.defaultdict(list)
    for r in rows:
        fams[r["family"]].append(r)
    quota = {"area_room": 10, "count_storey": 5, "count_model": 5, "area_total_storey": 2, "volume_walls": 2,
             "volume_slabs": 2, "length_walls": 2, "area_wall_side": 2}
    sample = []
    for fam, k in quota.items():
        sample += random.sample(fams[fam], k)
    out = []
    for r in sample:
        c = r["cands"]
        readings = {}
        if r["family"] in ("area_room", "area_total_storey"):
            readings = {"qto": c.get("qto_net"), "geom": c.get("geom_fp")}
            p = pdf.get((r["path"], r["parsed"].get("room")))
            if p:
                readings["pdf_polygon"] = p.get("area_bar")
        elif r["family"].startswith(("volume", "length", "area_wall")):
            qk = [k for k in c if k.startswith("qto_") and not k.endswith("_n") and "Gross" not in k][0]
            gk = [k for k in c if k.startswith("geom_")][0]
            readings = {"qto": c.get(qk), "geom": c.get(gk)}
        else:
            readings = {k: v for k, v in c.items() if isinstance(v, (int, float))}
        ref = r["ref"]
        tol = (lambda v: v is not None and int(v) == int(ref)) if r["type"] == "count" else (lambda v: v is not None and abs(v - ref) <= 0.02 * ref)
        ok = [k for k, v in readings.items() if tol(v)]
        present = [k for k, v in readings.items() if v is not None]
        verdict = "contradicted" if not ok else ("consistent" if len(ok) == len(present) else "convention")
        flags = []
        m = sem.get(r["model"])
        if m:
            st = m["storeys"].get(str(r["parsed"].get("storey")), {})
            if st.get("overlap_pairs"):
                flags.append(f"{st['overlap_pairs']} overlapping space pairs on storey")
            if st.get("nonroom_names"):
                flags.append("non-room spaces: " + ", ".join(st["nonroom_names"][:2]))
        out.append({"model": r["model"], "path": r["path"], "q": r["q"], "ref": ref,
                    "readings": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in readings.items()},
                    "agree": ok, "verdict": verdict, "flags": flags})
    return out


TOTAL = re.compile(r"Total\s+(Windows|Doors|Walls|Slabs|Stairs|Spaces|Columns|Beams|Members|Railings|Rooms)\s*:\s*(\d+)", re.I)
CLS = {"windows": "IfcWindow", "doors": "IfcDoor", "walls": "IfcWall", "slabs": "IfcSlab", "stairs": "IfcStair",
       "spaces": "IfcSpace", "rooms": "IfcSpace", "columns": "IfcColumn", "beams": "IfcBeam", "members": "IfcMember", "railings": "IfcRailing"}


def part_b():
    rows = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_bench/' in l]
    cache = {}
    out = []
    for r in rows:
        hits = TOTAL.findall(r["answer"])
        if not hits:
            continue
        fn = r["path"].split("/")[-1]
        q = r["question"].lower()
        # skip questions scoped to a level, a type subset or a part of the building
        if re.search(r"level|floor|storey|interior|exterior|structural|load|each|per |by level|ground|basement|roof", q):
            continue
        if fn not in cache:
            try:
                cache[fn] = ifcopenshell.open(str(DS / "data" / "ifc_bench" / fn))
            except Exception:  # noqa: BLE001
                cache[fn] = None
        f = cache[fn]
        if f is None:
            continue
        what, n = hits[0]
        cls = CLS[what.lower()]
        cnt = len(f.by_type(cls))
        top = sum(1 for e in f.by_type(cls) if not (e.Decomposes and e.Decomposes[0].RelatingObject.is_a(cls)))
        out.append({"file": fn, "q": r["question"], "stated": int(n), "class": cls, "by_type": cnt, "top_level": top,
                    "agree": int(n) in (cnt, top)})
    return out


def main():
    a = part_a()
    b = part_b()
    summ = {
        "A_n": len(a), "A_verdicts": dict(collections.Counter(x["verdict"] for x in a)),
        "B_n": len(b), "B_agree": sum(x["agree"] for x in b),
        "B_disagree": [x for x in b if not x["agree"]],
    }
    json.dump({"summary": summ, "A": a, "B": b}, open(OUT / "label_check.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summ.items() if k != "B_disagree"}))
    for x in a:
        print(x["verdict"][:5], x["model"][:22], "|", x["q"][:70], "| ref", x["ref"], x["readings"], x["flags"][:1])
    for x in summ["B_disagree"]:
        print("B", x["file"], "|", x["q"][:80], "| stated", x["stated"], x["class"], x["by_type"], x["top_level"])


if __name__ == "__main__":
    main()
