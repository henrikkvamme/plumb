# /// script
# requires-python = ">=3.11"
# dependencies = ["ifcopenshell==0.9.0.post1", "numpy", "shapely"]
# ///
"""Which IfcSpace objects did the generator ask about, and which are not real rooms?

Per model with room questions:
  - spaces per storey, spaces asked about (room-area questions), spaces not asked
  - spaces whose "LongName (Name)" key is not unique on its storey (the generator can not name them)
  - overlapping spaces on the same storey (intersection > 50% of the smaller footprint):
    duplicate space sets or gross-area spaces that the "rooms on the floor plan" count includes
  - spaces with names that suggest a non-room (gross area, roof, zone, shaft ...)
Writes out/space_semantics.json.
"""
import collections
import importlib.util
import json
import re
from pathlib import Path

import ifcopenshell

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "05_probe_models.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

NONROOM = re.compile(r"brutto|gross|roof|dach\b|zone|area\b|areal|bga|ngf|bgf|site|grundst|terrain|plot|outline|footprint", re.I)


def main():
    rows = [json.loads(l) for l in open(probe.DS / "questions.jsonl") if '"data/ifc_models/' in l]
    models = [p.name for p in probe.MD.glob("*.ifc") if not p.name.startswith("resbim")]
    asked = collections.defaultdict(set)
    room_count_q = collections.defaultdict(list)
    for r in rows:
        p = probe.parse(r)
        m = probe.model_of(r["path"], models)
        if p["family"] == "area_room":
            asked[m].add((p["storey"], p["room"]))
        if p["family"] in ("count_storey", "count_model") and p.get("cls") == "space":
            room_count_q[m].append((p.get("storey"), r["answer"]))
    out = {}
    for m in sorted(set(asked) | set(room_count_q)):
        f = ifcopenshell.open(str(probe.MD / m))
        geo = probe.geom_for(f, ["IfcSpace"], 1.0)
        spaces = f.by_type("IfcSpace")
        per = collections.defaultdict(list)
        for sp in spaces:
            st = probe.storey_of(sp)
            per[st.Name if st else None].append(sp)
        rec = {"n_spaces": len(spaces), "storeys": {}}
        for st, sps in per.items():
            keys = collections.Counter(f"{sp.LongName} ({sp.Name})" for sp in sps)
            fps = {}
            for sp in sps:
                g = geo.get(sp.GlobalId, {})
                fps[sp.GlobalId] = g
            # overlaps by footprint polygon
            import numpy as np  # noqa: F401
            polys = {}
            s = ifcopenshell.geom.settings()
            s.set("use-world-coords", True)
            for sp in sps:
                try:
                    sh = ifcopenshell.geom.create_shape(s, sp)
                    v = np.array(sh.geometry.verts).reshape(-1, 3)
                    fa = np.array(sh.geometry.faces).reshape(-1, 3)
                    polys[sp.GlobalId] = probe.footprint_poly(v, fa)
                except Exception:  # noqa: BLE001
                    polys[sp.GlobalId] = None
            overl = 0
            ids = [k for k, v in polys.items() if v is not None]
            ov_pairs = []
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = polys[ids[i]], polys[ids[j]]
                    if a.intersects(b):
                        inter = a.intersection(b).area
                        if inter > 0.5 * min(a.area, b.area):
                            overl += 1
                            if len(ov_pairs) < 3:
                                ov_pairs.append([f.by_guid(ids[i]).LongName, f.by_guid(ids[j]).LongName, round(inter, 2)])
            asked_here = {r for (s_, r) in asked[m] if s_ == st}
            nonunique = [k for k, c in keys.items() if c > 1]
            not_asked = [k for k in keys if k not in asked_here]
            rec["storeys"][str(st)] = {
                "n": len(sps), "asked": len(asked_here), "not_asked": len(not_asked),
                "not_asked_nonunique": sum(1 for k in not_asked if k in nonunique),
                "not_asked_no_geom": sum(1 for sp in sps if f"{sp.LongName} ({sp.Name})" in not_asked and polys.get(sp.GlobalId) is None),
                "nonunique_keys": len(nonunique), "overlap_pairs": overl, "overlap_examples": ov_pairs,
                "nonroom_names": [f"{sp.LongName} ({sp.Name})" for sp in sps if NONROOM.search(f"{sp.LongName} {sp.Name}")][:5],
                "no_name": sum(1 for sp in sps if not sp.LongName and not sp.Name),
            }
        rec["room_count_questions"] = room_count_q.get(m, [])
        out[m] = rec
        tot = {k: sum(v[k] for v in rec["storeys"].values()) for k in ("n", "asked", "not_asked", "not_asked_nonunique", "not_asked_no_geom", "overlap_pairs", "no_name")}
        rec["totals"] = tot
        print(m[:45], tot, flush=True)
    json.dump(out, open(probe.OUT / "space_semantics.json", "w"), indent=1, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
