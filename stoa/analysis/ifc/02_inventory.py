# /// script
# requires-python = ">=3.11"
# dependencies = ["ifcopenshell==0.9.0.post1"]
# ///
"""Inventory of every IFC file in ifc_models and ifc_bench.

Each file opens in its own subprocess, so the peak memory per file is measurable.
Writes out/inventory.jsonl (one line per file). Use --resbim N to include N ResBIM models (default 20).
Run: uv run 02_inventory.py [--resbim 500]
"""
import collections
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "junction-dataset" / "data"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

CLASSES = [
    "IfcSpace", "IfcWall", "IfcWallStandardCase", "IfcCurtainWall", "IfcSlab", "IfcRoof", "IfcDoor", "IfcWindow",
    "IfcColumn", "IfcBeam", "IfcStair", "IfcStairFlight", "IfcRamp", "IfcRailing", "IfcCovering", "IfcFooting",
    "IfcPile", "IfcMember", "IfcPlate", "IfcBuildingElementProxy", "IfcFurnishingElement", "IfcFlowTerminal",
    "IfcSanitaryTerminal", "IfcLightFixture", "IfcFlowSegment", "IfcFlowFitting", "IfcDistributionElement",
    "IfcOpeningElement", "IfcZone", "IfcAnnotation", "IfcGrid",
]


def one(path: str) -> dict:
    import ifcopenshell

    p = Path(path)
    t0 = time.perf_counter()
    f = ifcopenshell.open(path)
    t_open = time.perf_counter() - t0
    rec = {"file": f"{p.parent.name}/{p.name}", "bytes": p.stat().st_size, "schema": f.schema, "open_s": round(t_open, 2)}
    try:
        h = f.header.file_name
        rec["originating_system"] = h.originating_system
        rec["preprocessor"] = h.preprocessor_version
    except Exception as e:  # noqa: BLE001
        rec["header_error"] = str(e)
    apps = set()
    for a in f.by_type("IfcApplication"):
        apps.add(f"{a.ApplicationFullName} {a.Version}")
    rec["applications"] = sorted(apps)
    counts = {}
    for c in CLASSES:
        try:
            counts[c] = len(f.by_type(c))
        except Exception:  # noqa: BLE001  class absent in this schema
            counts[c] = None
    rec["counts"] = counts
    rec["n_entities"] = f.by_id(1) and len(list(f))
    storeys = []
    for s in f.by_type("IfcBuildingStorey"):
        storeys.append({"name": s.Name, "elev": s.Elevation})
    rec["storeys"] = storeys
    rec["n_buildings"] = len(f.by_type("IfcBuilding"))
    # quantity sets
    qto = collections.Counter()
    for eq in f.by_type("IfcElementQuantity"):
        qto[eq.Name] += 1
    rec["qto_sets"] = dict(qto.most_common(15))
    pset = collections.Counter()
    for ps in f.by_type("IfcPropertySet"):
        pset[ps.Name] += 1
    rec["n_psets"] = sum(pset.values())
    rec["n_pset_names"] = len(pset)
    rec["top_psets"] = dict(pset.most_common(8))
    # spaces with an area quantity
    n_sp_q = 0
    for sp in f.by_type("IfcSpace"):
        ok = False
        for rel in getattr(sp, "IsDefinedBy", []) or []:
            if rel.is_a("IfcRelDefinesByProperties"):
                d = rel.RelatingPropertyDefinition
                if d.is_a("IfcElementQuantity") and any(q.is_a("IfcQuantityArea") for q in d.Quantities):
                    ok = True
        n_sp_q += ok
    rec["spaces_with_area_qto"] = n_sp_q
    rec["units"] = []
    for ua in f.by_type("IfcUnitAssignment")[:1]:
        for u in ua.Units:
            if u.is_a("IfcSIUnit"):
                rec["units"].append(f"{u.UnitType}:{u.Prefix or ''}{u.Name}")
            elif u.is_a("IfcConversionBasedUnit"):
                rec["units"].append(f"{u.UnitType}:{u.Name}")
    rec["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1)  # macOS: bytes
    rec["total_s"] = round(time.perf_counter() - t0, 2)
    rec["md5"] = hashlib.md5(p.read_bytes()).hexdigest()
    return rec


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2]), ensure_ascii=False, default=str))
        return
    n_res = 20
    if "--resbim" in sys.argv:
        n_res = int(sys.argv[sys.argv.index("--resbim") + 1])
    files = sorted(p for p in (ROOT / "ifc_models").glob("*.ifc") if not p.name.startswith("resbim"))
    res = sorted((ROOT / "ifc_models").glob("resbim-*_model.ifc"), key=lambda p: int(p.name.split("-")[1].split("_")[0]))
    files += res[:n_res]
    files += sorted((ROOT / "ifc_bench").glob("*.ifc"))
    out = open(OUT / "inventory.jsonl", "w")
    for p in files:
        r = subprocess.run([sys.executable, __file__, "--one", str(p)], capture_output=True, text=True)
        if r.returncode != 0:
            rec = {"file": f"{p.parent.name}/{p.name}", "error": r.stderr[-400:]}
        else:
            rec = json.loads(r.stdout.strip().splitlines()[-1])
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        print(rec["file"], rec.get("schema"), rec.get("open_s"), rec.get("peak_rss_mb"), flush=True)


if __name__ == "__main__":
    main()
