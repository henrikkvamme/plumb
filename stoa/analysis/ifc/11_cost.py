# /// script
# requires-python = ">=3.11"
# dependencies = ["ifcopenshell==0.9.0.post1", "numpy", "shapely"]
# ///
"""Cost of the IFC path: time and peak memory to open, query and tessellate the largest models.

Each model runs in its own subprocess. Steps: open; by_type counts of 9 classes; storey assignment of all
walls; all Qto values of all walls; geometry (ifcopenshell.geom iterator, 8 threads) of IfcSpace, IfcWall,
IfcSlab. Peak RSS from getrusage (macOS reports bytes). Writes out/cost.jsonl.
Machine facts go in the record (CPU count, platform).
"""
import json
import multiprocessing
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset" / "data"
MODELS = [
    "ifc_bench/sixty5_arc.ifc", "ifc_bench/sixty5_plumbing.ifc", "ifc_bench/sixty5_ventilation.ifc",
    "ifc_models/bimspeed-barlad_ro-arc-m3-e-pth-0000.ifc", "ifc_models/bsc-molio_molio-with-uris.ifc",
    "ifc_bench/hitos_arc.ifc", "ifc_models/bsc-clinic_clinic-architectural.ifc", "ifc_models/kit-fzk-haus_ac20-fzk-haus.ifc",
]


def one(path):
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element as ue

    rec = {"file": path, "mb": round((DS / path).stat().st_size / 1e6, 1), "cpus": multiprocessing.cpu_count(), "machine": platform.machine()}
    t = time.perf_counter()
    f = ifcopenshell.open(str(DS / path))
    rec["open_s"] = round(time.perf_counter() - t, 2)
    rec["rss_after_open_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6)
    t = time.perf_counter()
    counts = {c: len(f.by_type(c)) for c in ["IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcSpace", "IfcColumn", "IfcBeam", "IfcStair", "IfcFlowTerminal"]}
    rec["by_type_s"] = round(time.perf_counter() - t, 3)
    rec["counts"] = counts
    t = time.perf_counter()
    walls = f.by_type("IfcWall")
    _ = [ue.get_container(w) for w in walls]
    _ = [ue.get_psets(w, qtos_only=True) for w in walls]
    rec["walls_storey_qto_s"] = round(time.perf_counter() - t, 2)
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    els = f.by_type("IfcSpace") + walls + f.by_type("IfcSlab")
    rec["n_geom_elems"] = len(els)
    t = time.perf_counter()
    n = 0
    if els:
        it = ifcopenshell.geom.iterator(s, f, 8, include=els)
        if it.initialize():
            while True:
                n += 1
                if not it.next():
                    break
    rec["geom_s"] = round(time.perf_counter() - t, 2)
    rec["n_geom_done"] = n
    rec["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6)
    return rec


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2])))
        return
    out = open(HERE / "out" / "cost.jsonl", "w")
    for m in MODELS:
        t = time.perf_counter()
        r = subprocess.run([sys.executable, __file__, "--one", m], capture_output=True, text=True)
        rec = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"file": m, "error": r.stderr[-300:]}
        rec["wall_s_incl_import"] = round(time.perf_counter() - t, 2)
        out.write(json.dumps(rec) + "\n")
        out.flush()
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
