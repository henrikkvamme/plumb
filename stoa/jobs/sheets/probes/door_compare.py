"""Door boxes of both detectors and the vector door leaves on one sheet; contact sheets of each disagreement."""
import sys, json
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS=None
from bp.tools import symbol_detector as sd
S=Path(sys.argv[1]); pdf=sys.argv[2]; png=sys.argv[3]; ratio=float(sys.argv[4]); tag=sys.argv[5]
page=pymupdf.open(pdf)[0]
img=Image.open(png).convert("RGB")
k=img.width/page.rect.width
MM=25.4/72*ratio
leaves=[]
for d in page.get_drawings():
    it=d["items"]
    if not (7<=len(it)<=14) or any(i[0]!="l" for i in it): continue
    rc=d["rect"]; w,h=rc.width*MM,rc.height*MM
    if abs(w-h)<=0.12*max(w,h) and 550<=max(w,h)<=1300:
        leaves.append([rc.x0*k,rc.y0*k,rc.x1*k,rc.y1*k])
boxes={}
for m in ("yolo26m","yolo26m-styles"):
    det=sd.Detector.get(Path("artifacts/cubicasa-detect")/m)
    all_=det.detect(img)
    boxes[m]=[list(d.box) for d in sd.count(all_,("door",),det.thresholds)]
    boxes[m+"-window"]=[list(d.box) for d in sd.count(all_,("window",),det.thresholds)]
def c(b): return ((b[0]+b[2])/2,(b[1]+b[3])/2)
def inside(pt,b,m=0.3):
    g=m*max(b[2]-b[0],b[3]-b[1]); return b[0]-g<=pt[0]<=b[2]+g and b[1]-g<=pt[1]<=b[3]+g
A,B=boxes["yolo26m"],boxes["yolo26m-styles"]
both=[a for a in A if any(inside(c(b),a,0) or inside(c(a),b,0) for b in B)]
a_only=[a for a in A if a not in both]
b_only=[b for b in B if not any(inside(c(b),a,0) or inside(c(a),b,0) for a in A)]
both_leaf=[a for a in both if any(inside(c(l),a) for l in leaves)]
both_noleaf=[a for a in both if a not in both_leaf]
leaf_nobox=[l for l in leaves if not any(inside(c(l),b) for b in A+B)]
print(tag,"leaves",len(leaves),"A",len(A),"B",len(B),"both",len(both),"both+leaf",len(both_leaf),"both no leaf",len(both_noleaf),"A only",len(a_only),"B only",len(b_only),"leaf no box",len(leaf_nobox),"windows",len(boxes["yolo26m-window"]),len(boxes["yolo26m-styles-window"]))
json.dump({"leaves":leaves,**boxes},open(S/f"doorkey-{tag}.json","w"))
def sheet(name, bs, half=260, cols=6):
    if not bs: return
    out=Image.new("RGB",(cols*360,((len(bs)+cols-1)//cols)*360),"white")
    for i,b in enumerate(bs):
        x,y=c(b); t=img.crop((int(x-half),int(y-half),int(x+half),int(y+half)))
        dr=ImageDraw.Draw(t); dr.rectangle((b[0]-x+half,b[1]-y+half,b[2]-x+half,b[3]-y+half),outline=(255,0,0),width=3)
        t=t.resize((356,356)); ImageDraw.Draw(t).text((4,4),str(i),fill=(0,0,255))
        out.paste(t,((i%cols)*360+2,(i//cols)*360+2))
    out.save(S/f"dk-{tag}-{name}.jpg",quality=85)
sheet("both-noleaf",both_noleaf); sheet("a-only",a_only); sheet("b-only",b_only); sheet("leaf-nobox",leaf_nobox)
