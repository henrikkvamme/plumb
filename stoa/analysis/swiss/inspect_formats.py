# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf", "ezdxf", "pillow"]
# ///
"""Describe what each format holds for a few swiss_dwellings floors.

Writes out/inspect_<floor>.json with PDF metadata, page size, text spans, drawing counts, OCGs (layers),
images; DXF header units, layers, entity counts per layer, blocks and text samples; PNG size and dpi.
Usage: uv run inspect_formats.py [floor ...]
"""
import sys, json, pathlib, collections
import fitz, ezdxf
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"  # git-ignored; derived from licensed data
OUT.mkdir(exist_ok=True)

floors = sys.argv[1:] or ["site3387_bldg5238_floor23498"]
for f in floors:
    res = {"floor": f}
    doc = fitz.open(D / f"{f}.pdf")
    pg = doc[0]
    res["pdf"] = {
        "pages": len(doc),
        "metadata": doc.metadata,
        "page_rect_pt": list(pg.rect),
        "page_mm": [round(pg.rect.width / 72 * 25.4, 1), round(pg.rect.height / 72 * 25.4, 1)],
        "ocgs": doc.get_ocgs(),
        "images": len(pg.get_images()),
        "n_drawings": len(pg.get_drawings()),
        "fonts": pg.get_fonts(),
    }
    spans = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                spans.append({"t": s["text"], "size": round(s["size"], 2), "bbox": [round(x, 1) for x in s["bbox"]], "color": s["color"]})
    res["pdf"]["spans"] = spans
    dr = pg.get_drawings()
    res["pdf"]["drawing_styles"] = collections.Counter(
        f"fill={d.get('fill')} color={d.get('color')} w={round(d.get('width') or 0, 2)} type={d['type']} layer={d.get('layer')}" for d in dr
    ).most_common(40)
    # DXF
    dx = ezdxf.readfile(D / f"{f}.dxf")
    msp = dx.modelspace()
    res["dxf"] = {
        "version": dx.dxfversion,
        "insunits": dx.header.get("$INSUNITS"),
        "measurement": dx.header.get("$MEASUREMENT"),
        "extmin": list(dx.header.get("$EXTMIN", (0, 0, 0))),
        "extmax": list(dx.header.get("$EXTMAX", (0, 0, 0))),
        "layers": [l.dxf.name for l in dx.layers],
        "blocks": [b.name for b in dx.blocks if not b.name.startswith("*")],
        "entities_by_layer_type": collections.Counter(f"{e.dxf.layer}|{e.dxftype()}" for e in msp).most_common(),
        "inserts_by_block": collections.Counter(e.dxf.name for e in msp if e.dxftype() == "INSERT").most_common(),
        "texts": [(e.dxf.layer, e.dxftype(), e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text) for e in msp if e.dxftype() in ("TEXT", "MTEXT")][:400],
        "xdata_apps": sorted({a for e in msp for a in (e.xdata.data.keys() if e.xdata else [])}),
    }
    blocks = {}
    for b in dx.blocks:
        if b.name.startswith("*"):
            continue
        blocks[b.name] = collections.Counter(e.dxftype() for e in b).most_common()
    res["dxf"]["block_contents"] = blocks
    im = Image.open(D / f"{f}.png")
    res["png"] = {"size": im.size, "mode": im.mode, "info": {k: str(v) for k, v in im.info.items()}}
    json.dump(res, open(OUT / f"inspect_{f}.json", "w"), indent=1, ensure_ascii=False, default=str)
    print(f, "pdf spans", len(spans), "drawings", res["pdf"]["n_drawings"], "dxf layers", len(res["dxf"]["layers"]), "png", im.size)
