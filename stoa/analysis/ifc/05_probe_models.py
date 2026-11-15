# /// script
# requires-python = ">=3.11"
# dependencies = ["ifcopenshell==0.9.0.post1", "numpy", "shapely"]
# ///
"""Probe: which rule reproduces Stoa's reference answers for the ifc_models templates?

For each of the 3,062 ifc_models questions it parses the template (family, element class, storey, room),
then computes several candidate answers from the IFC model:
  - quantities from Qto/BaseQuantities sets (NetFloorArea, GrossFloorArea, NetVolume, Length, NetSideArea ...)
  - an "Area" value from any property set (Revit PSet_Revit_Dimensions, ArchiCAD)
  - geometry from ifcopenshell.geom (footprint area, volume, footprint long side)
  - counts with several storey and class rules
A candidate agrees when it is within 2% (areas, volumes, lengths) or exact (counts).
Writes out/probe_rows.jsonl and out/probe_summary.json.
Run: uv run 05_probe_models.py [model-substring ...]
"""
import collections
import json
import multiprocessing
import re
import sys
import time
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.shape as us
import ifcopenshell.util.unit as uu
import numpy as np
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
MD = DS / "data" / "ifc_models"
OUT = HERE / "out"

QUOTE = re.compile(r"'([^']*)'|„([^“”]*)[“”]|«([^»]*)»|\"([^\"]*)\"")

# element class words, checked in order (first hit wins)
CLASS_WORDS = [
    ("sanitary", ["sanitary", "sanitär", "sanitair"]),
    ("light", ["light fixture", "iluminat", "leuchte"]),
    ("door", ["door", "tür", "deur", "puerta", "døre", "dør", " ust ", "drzwi", "porte", "uși"]),
    ("window", ["window", "fenster", "ramen", "raam", "ventana", "vindue", "akent", "okien", "finestr", "ferestre"]),
    ("stair", ["stair", "treppe", "trap", "escalera", "treppi", "schod", "scări"]),
    ("column", ["column", "stütze", "kolom", "pilar", "søjle", "posti", "stâlp"]),
    ("beam", ["beam", "träger", "balk", "viga", "bjælke", "tala", "belek", "grinzi"]),
    ("wall", ["wall", "wände", "wand", "muro", "muri", "væg", "vægge", "sein", "ścian", "pereți"]),
    ("space", ["room", "räume", "ruimte", "local", " rum", "ruumi", "pomieszcze", "spaces"]),
]


def quotes(q):
    return [next(x for x in m if x) if any(m) else "" for m in QUOTE.findall(q)]


def parse(r):
    q = r["question"]
    ql = " " + q.lower() + " "
    qs = quotes(q)
    t = r["type"]
    d = {"type": t, "quotes": qs}
    if t == "area":
        if len(qs) >= 2:
            d.update(family="area_room", room=qs[0], storey=qs[1])
        elif "seiten" in ql or "side" in ql or "zijopp" in ql or "sideareal" in ql:
            d.update(family="area_wall_side", storey=qs[0] if qs else None)
        else:
            d.update(family="area_total_storey", storey=qs[0] if qs else None)
    elif t == "volume":
        slab = any(w in ql for w in ["slab", "decke", "vloer", "dæk", "losa", "plaat"])
        d.update(family="volume_slabs" if slab else "volume_walls", storey=qs[0] if qs else None)
    elif t == "length":
        d.update(family="length_walls", storey=qs[0] if qs else None)
    elif t == "count":
        cls = next((c for c, ws in CLASS_WORDS if any(w in ql for w in ws)), None)
        model_scope = any(w in ql for w in [" model", "modell", "modelo", "modèle", "modello", "modelul", "mudel", "modelu"])
        d.update(family="count_model" if model_scope else "count_storey", cls=cls, storey=None if model_scope else (qs[0] if qs else None))
    return d


def qto_values(el):
    out = collections.defaultdict(list)
    for pname, props in ue.get_psets(el, qtos_only=True).items():
        for k, v in props.items():
            if isinstance(v, (int, float)) and k != "id":
                out[k].append((pname, float(v)))
    return out


def pset_area(el):
    for pname, props in ue.get_psets(el, psets_only=True).items():
        for k, v in props.items():
            if k in ("Area", "Fläche", "Oppervlakte", "Area (Net)") and isinstance(v, (int, float)):
                return float(v)
    return None


def storey_of(el):
    c = ue.get_container(el)
    if c is None:
        a = ue.get_aggregate(el)
        while a is not None and not a.is_a("IfcBuildingStorey"):
            c2 = ue.get_container(a)
            a = c2 if c2 is not None else ue.get_aggregate(a)
        return a
    while c is not None and not c.is_a("IfcBuildingStorey"):
        c = ue.get_aggregate(c)
    return c


CLASSES = {
    "door": ["IfcDoor"], "window": ["IfcWindow"], "wall": ["IfcWall"], "space": ["IfcSpace"], "column": ["IfcColumn"],
    "beam": ["IfcBeam"], "stair": ["IfcStair"], "sanitary": ["IfcSanitaryTerminal"], "light": ["IfcLightFixture"],
}


def by_type_safe(f, c):
    try:
        return f.by_type(c)
    except RuntimeError:
        return []


def footprint_poly(verts, faces):
    tris = verts[faces][:, :, :2]
    polys = []
    for t in tris:
        p = Polygon(t)
        if p.area > 1e-9:
            polys.append(p)
    if not polys:
        return None
    return unary_union(polys)


def geom_for(f, classes, scale):
    """Run the geometry iterator over the given classes. Returns {guid: dict(area_fp, volume, long_side, top_area)}."""
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    res = {}
    els = []
    for c in classes:
        els += by_type_safe(f, c)
    if not els:
        return res
    it = ifcopenshell.geom.iterator(s, f, min(8, multiprocessing.cpu_count()), include=els)
    if not it.initialize():
        return res
    while True:
        sh = it.get()
        try:
            g = sh.geometry
            v = np.array(g.verts).reshape(-1, 3)
            fa = np.array(g.faces).reshape(-1, 3)
            if len(fa):
                fp = footprint_poly(v, fa)
                vol = us.get_volume(g)
                rect = fp.minimum_rotated_rectangle if fp is not None else None
                long_side = None
                if rect is not None and rect.geom_type == "Polygon":
                    xs = np.array(rect.exterior.coords)
                    sides = np.linalg.norm(np.diff(xs, axis=0), axis=1)
                    long_side = float(sides.max())
                # area of faces that point up (top faces) and down
                tri = v[fa]
                n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
                a = np.linalg.norm(n, axis=1) / 2
                nz = np.divide(n[:, 2], 2 * a, out=np.zeros_like(a), where=a > 0)
                up = float(a[nz > 0.99].sum())
                side = float(a[np.abs(nz) < 0.01].sum())
                res[sh.guid] = {
                    "fp": fp.area if fp is not None else None, "vol": float(vol), "long": long_side, "up": up, "side": side,
                    "zmin": float(v[:, 2].min()), "zmax": float(v[:, 2].max()),
                }
        except Exception as e:  # noqa: BLE001
            res[sh.guid] = {"err": str(e)[:80]}
        if not it.next():
            break
    return res


def agree(cand, ref, t):
    if cand is None:
        return False
    if t == "count":
        return int(round(cand)) == int(ref)
    return abs(cand - ref) <= 0.02 * abs(ref) if ref else abs(cand) < 1e-6


def probe_model(model_file, rows):
    t0 = time.perf_counter()
    f = ifcopenshell.open(str(MD / model_file))
    t_open = time.perf_counter() - t0
    lscale = uu.calculate_unit_scale(f)  # project length unit to metres
    storeys = {}
    for s in f.by_type("IfcBuildingStorey"):
        storeys.setdefault(s.Name, []).append(s)
    families = {parse(r)["family"] for r in rows}
    need_geom = []
    if families & {"area_room", "area_total_storey"}:
        need_geom.append("IfcSpace")
    if families & {"volume_walls", "length_walls", "area_wall_side"}:
        need_geom.append("IfcWall")
    if "volume_slabs" in families:
        need_geom.append("IfcSlab")
    t1 = time.perf_counter()
    geo = geom_for(f, need_geom, lscale)
    t_geom = time.perf_counter() - t1
    # spaces index
    spaces = by_type_safe(f, "IfcSpace")
    sp_index = collections.defaultdict(list)
    for sp in spaces:
        keys = {f"{sp.LongName} ({sp.Name})", f"{sp.Name} ({sp.LongName})", f"{sp.Name}", f"{sp.LongName}"}
        for k in keys:
            sp_index[k].append(sp)

    def space_cands(sp):
        q = qto_values(sp)
        g = geo.get(sp.GlobalId, {})
        c = {
            "qto_net": q["NetFloorArea"][0][1] if q.get("NetFloorArea") else None,
            "qto_gross": q["GrossFloorArea"][0][1] if q.get("GrossFloorArea") else None,
            "pset_area": pset_area(sp),
            "geom_fp": g.get("fp"),
            "geom_up": g.get("up"),
        }
        return c

    def storey_elems(storey_name, ifc_classes, rule):
        sts = storeys.get(storey_name, [])
        out = []
        for c in ifc_classes:
            for el in by_type_safe(f, c):
                st = storey_of(el)
                if rule == "contained_direct":
                    cont = ue.get_container(el)
                    if cont is not None and cont in sts:
                        out.append(el)
                elif st in sts:
                    out.append(el)
        return out

    results = []
    for r in rows:
        p = parse(r)
        fam = p["family"]
        ref = r["answer"]
        cands = {}
        info = {}
        try:
            if fam == "area_room":
                m = sp_index.get(p["room"], [])
                # restrict to storey if several
                if len(m) > 1:
                    m2 = [sp for sp in m if storey_of(sp) in storeys.get(p["storey"], [])]
                    m = m2 or m
                info["n_match"] = len(m)
                if m:
                    cands = space_cands(m[0])
            elif fam == "area_total_storey":
                sps = [sp for sp in spaces if storey_of(sp) in storeys.get(p["storey"], [])]
                info["n_spaces"] = len(sps)
                cs = [space_cands(sp) for sp in sps]
                for k in ["qto_net", "qto_gross", "pset_area", "geom_fp", "geom_up"]:
                    vals = [c[k] for c in cs]
                    cands[k] = sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
                    cands[k + "_complete"] = all(v is not None for v in vals)
            elif fam in ("volume_walls", "length_walls", "area_wall_side", "volume_slabs"):
                cls = ["IfcSlab"] if fam == "volume_slabs" else ["IfcWall"]
                els = storey_elems(p["storey"], cls, "storey")
                info["n_elems"] = len(els)
                qk = {"volume_walls": ["NetVolume", "GrossVolume"], "volume_slabs": ["NetVolume", "GrossVolume"],
                      "length_walls": ["Length"], "area_wall_side": ["NetSideArea", "GrossSideArea"]}[fam]
                for k in qk:
                    vals = []
                    for el in els:
                        qv = qto_values(el).get(k)
                        vals.append(qv[0][1] if qv else None)
                    s = sum(v for v in vals if v is not None)
                    if k == "Length":
                        s = s * lscale if s > 0 else s
                    cands["qto_" + k] = s if any(v is not None for v in vals) else None
                    cands["qto_" + k + "_n"] = sum(v is not None for v in vals)
                gk = {"volume_walls": "vol", "volume_slabs": "vol", "length_walls": "long", "area_wall_side": "side"}[fam]
                gv = [geo.get(el.GlobalId, {}).get(gk) for el in els]
                cands["geom_" + gk] = sum(v for v in gv if v) if any(gv) else None
                if fam == "area_wall_side":
                    cands["geom_side_half"] = cands["geom_side"] / 2 if cands.get("geom_side") else None
            elif fam in ("count_model", "count_storey"):
                cls = p["cls"]
                info["cls"] = cls
                base = CLASSES.get(cls, [])
                alt = {
                    "stair": ["IfcStair", "IfcStairFlight"], "wall": ["IfcWall", "IfcCurtainWall"],
                    "sanitary": ["IfcSanitaryTerminal", "IfcFlowTerminal"], "light": ["IfcLightFixture", "IfcFlowTerminal"],
                    "column": ["IfcColumn", "IfcMember"], "beam": ["IfcBeam", "IfcMember"], "door": ["IfcDoor"], "window": ["IfcWindow"],
                    "space": ["IfcSpace"],
                }.get(cls, base)
                if fam == "count_model":
                    cands["by_type"] = sum(len(by_type_safe(f, c)) for c in base)
                    cands["by_type_alt"] = sum(len(by_type_safe(f, c)) for c in alt)
                    if cls == "stair":
                        cands["stair_flights"] = len(by_type_safe(f, "IfcStairFlight"))
                    if cls in ("sanitary", "light"):
                        # IFC2X3: FlowTerminal with a type name that mentions it
                        cands["flowterminal_typed"] = sum(1 for e in by_type_safe(f, "IfcFlowTerminal") if ue.get_type(e) is not None and (("sanit" in (ue.get_type(e).is_a() + (ue.get_type(e).Name or "")).lower()) if cls == "sanitary" else ("light" in ue.get_type(e).is_a().lower())))
                    # top-level only (not part of an aggregate)
                    cands["by_type_toplevel"] = sum(1 for c in base for e in by_type_safe(f, c) if ue.get_aggregate(e) is None or ue.get_aggregate(e).is_a("IfcSpatialStructureElement") or ue.get_aggregate(e).is_a("IfcSpatialElement"))
                else:
                    cands["storey_any"] = len(storey_elems(p["storey"], base, "storey"))
                    cands["contained_direct"] = len(storey_elems(p["storey"], base, "contained_direct"))
                    cands["storey_alt"] = len(storey_elems(p["storey"], alt, "storey"))
                    if cls == "stair":
                        cands["stair_flights"] = len(storey_elems(p["storey"], ["IfcStairFlight"], "storey"))
                    if cls == "space":
                        cands["space_with_geom"] = sum(1 for sp in storey_elems(p["storey"], ["IfcSpace"], "storey") if geo.get(sp.GlobalId, {}).get("fp"))
        except Exception as e:  # noqa: BLE001
            info["error"] = repr(e)[:200]
        agrees = sorted(k for k, v in cands.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and not k.endswith("_n") and agree(v, ref, r["type"]))
        results.append({"path": r["path"].split("/")[-1], "q": r["question"], "ref": ref, "type": r["type"], "family": fam,
                        "parsed": {k: v for k, v in p.items() if k not in ("quotes",)}, "cands": cands, "info": info, "agrees": agrees})
    timing = {"model": model_file, "open_s": round(t_open, 2), "geom_s": round(t_geom, 2), "n_geom": len(geo), "geom_classes": need_geom}
    return results, timing


def model_of(path, models):
    name = path.split("/")[-1]
    if name.endswith(".ifc"):
        return name
    return max((m for m in models if name.startswith(m[:-4] + "_")), key=len)


def main():
    rows = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_models/' in l]
    models = [p.name for p in MD.glob("*.ifc") if not p.name.startswith("resbim")]
    by_model = collections.defaultdict(list)
    for r in rows:
        by_model[model_of(r["path"], models)].append(r)
    sel = sys.argv[1:]
    out_rows = open(OUT / ("probe_rows.jsonl" if not sel else "probe_rows_partial.jsonl"), "w")
    timings = []
    for m, rs in sorted(by_model.items(), key=lambda kv: len(kv[1])):
        if sel and not any(s in m for s in sel):
            continue
        t0 = time.perf_counter()
        res, tm = probe_model(m, rs)
        tm["total_s"] = round(time.perf_counter() - t0, 2)
        timings.append(tm)
        for x in res:
            x["model"] = m
            out_rows.write(json.dumps(x, ensure_ascii=False, default=str) + "\n")
        out_rows.flush()
        print(m, len(rs), tm, flush=True)
    json.dump(timings, open(OUT / ("probe_timings.json" if not sel else "probe_timings_partial.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
