"""The 500 resbim IFC+PNG pairs have no public questions. Can the IFC give exact truth for new questions?"""
import glob, random, collections, os, statistics
import ifcopenshell, ifcopenshell.util.element as ue
from common import ROOT
random.seed(4)
fs = random.sample(sorted(glob.glob(ROOT + "/data/ifc_models/resbim-*.ifc")), 25)
tot = collections.Counter(); spaces_with_area = 0; spaces = 0; first = True; ns = []
for f in fs:
    m = ifcopenshell.open(f)
    c = {t: len(m.by_type(t)) for t in ("IfcSpace","IfcDoor","IfcWindow","IfcWall","IfcSlab","IfcBuildingStorey","IfcColumn","IfcStair")}
    for k, v in c.items(): tot[k] += v
    ns.append(c["IfcSpace"])
    for s in m.by_type("IfcSpace"):
        spaces += 1; ps = ue.get_psets(s); a = [v for p in ps.values() for k, v in p.items() if "area" in k.lower() and isinstance(v, (int, float))]
        spaces_with_area += bool(a)
        if first: print("example space", s.Name, s.LongName, {k: {kk: vv for kk, vv in v.items() if kk != "id"} for k, v in list(ps.items())[:3]})
        first = False
print("schema", m.schema)
print("25 models, element totals", dict(tot)); print("spaces per model min/median/max", min(ns), statistics.median(ns), max(ns), "| spaces with an area quantity", spaces_with_area, "/", spaces)
