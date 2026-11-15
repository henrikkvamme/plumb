"""Peek at one Swiss DXF: layers, entity types, text. Checks what the sibling format leaks."""
import sys, collections, ezdxf
from common import ROOT
d = ezdxf.readfile(ROOT + "/data/swiss_dwellings/site3387_bldg5238_floor23498.dxf")
ms = d.modelspace(); c = collections.Counter((e.dxf.layer, e.dxftype()) for e in ms)
for k, n in sorted(c.items()): print(n, k)
print("units", d.header.get("$INSUNITS"), "blocks", [b.name for b in d.blocks if not b.name.startswith("*")][:20])
ts = [e for e in ms if e.dxftype() in ("TEXT","MTEXT")]
print([ (e.dxf.layer, (e.dxf.text if e.dxftype()=="TEXT" else e.text)[:25]) for e in ts[:14]])
