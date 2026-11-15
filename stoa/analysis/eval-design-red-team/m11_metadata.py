"""What metadata a solver could read instead of the drawing. Compact output."""
import glob, random, collections, os, re, sys
import fitz
from PIL import Image
from common import ROOT
Image.MAX_IMAGE_PIXELS = None
random.seed(2)
D = ROOT + "/data"
# swiss PDFs: metadata, page size, where the scale text sits
fs = random.sample(sorted(glob.glob(D + "/swiss_dwellings/*.pdf")), 100)
sizes = collections.Counter(); meta = collections.Counter(); ys = []; scale = collections.Counter(); ids = 0; srcnote = 0
for f in fs:
    d = fitz.open(f); p = d[0]; sizes[(round(p.rect.width), round(p.rect.height), len(d))] += 1
    m = d.metadata; meta[(m.get("producer","")[:30], m.get("creator","")[:30], m.get("title","")[:40])] += 1
    t = p.get_text()
    for b in p.get_text("blocks"):
        if re.search(r"Massstab|Échelle|Echelle|Scala|Scale", b[4]): ys.append(b[1]/p.rect.height)
    mm = re.search(r"1\s*:\s*(\d+)", t); scale[mm.group(1) if mm else "none"] += 1
    b = os.path.basename(f); sid, bid, fid = re.match(r"site(\d+)_bldg(\d+)_floor(\d+)", b).groups()
    ids += (bid in t and fid in t); srcnote += ("Swiss Dwellings" in t)
print("swiss page (w,h,pages)", dict(sizes)); print("swiss metadata (producer,creator,title)", meta.most_common(3))
print("swiss scale denominators", dict(scale), "| scale text y/H min..max %.3f..%.3f" % (min(ys), max(ys)), "| sheets whose text holds the public building id and floor id:", ids, "/100", "| names the public source:", srcnote, "/100")
# ifc_models plan PDFs
fs = sorted(glob.glob(D + "/ifc_models/*_plan*.pdf")); meta = collections.Counter(); note = 0; sc = collections.Counter()
for f in fs:
    d = fitz.open(f); t = d[0].get_text(); m = d.metadata; meta[(m.get("producer","")[:30], m.get("creator","")[:30])] += 1
    note += bool(re.search(r"\.ifc", t)); mm = re.search(r"1\s*:\s*(\d+)", t); sc[mm.group(1) if mm else "none"] += 1
print("ifc plan pdfs", len(fs), "metadata", meta.most_common(2), "| footer names the .ifc file:", note, "| scale", dict(sc))
# PNG text chunks / EXIF
def info(f):
    im = Image.open(f); k = set(im.info.keys()) - {"dpi","jfif","jfif_version","jfif_unit","jfif_density","icc_profile","progressive","progression","transparency","gamma","aspect","srgb","chromaticity","adobe","adobe_transform"}
    ex = 0
    try: ex = len(im.getexif())
    except Exception: pass
    return tuple(sorted(k)), ex, im.size
for s, ext in (("cubicasa5k","png"),("swiss_dwellings","png"),("habs","jpg"),("finna","jpg"),("europeana","jpg"),("wikimedia","jpg")):
    fs = random.sample(sorted(glob.glob(f"{D}/{s}/*.{ext}")), 60); c = collections.Counter(); exn = 0; W = []
    for f in fs:
        k, ex, sz = info(f); c[k] += 1; exn += ex > 0; W.append(max(sz))
    W.sort(); print(f"{s}: info keys {dict(c)} | files with EXIF {exn}/60 | long side p10/50/90 {W[6]}/{W[30]}/{W[54]}")
# opening_design PDFs: page counts
fs = glob.glob(D + "/opening_design/**/*.pdf", recursive=True); pc = collections.Counter(); proj = collections.Counter()
for f in fs:
    try: pc[min(len(fitz.open(f)), 6)] += 1
    except Exception: pc["err"] += 1
    proj[f.split("/opening_design/")[1].split("/")[0]] += 1
print("opening_design pdfs", len(fs), "pages hist (6 = 6+)", sorted(pc.items(), key=str), "| projects", len(proj), proj.most_common(6))
