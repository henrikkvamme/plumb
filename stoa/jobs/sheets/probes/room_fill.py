import sys, json, re
from collections import defaultdict
import numpy as np, cv2
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
from bp.tools import ocr, sheet_text
S=sys.argv[1]; REACH=float(sys.argv[2]); KEEP=float(sys.argv[3])
f=S+"/stoa-examples/uk_dfe_sen-dfe-xx-00-d-x-0201-special_school_plan_level_00-a-c01_p001.png"
rgb=ocr.to_rgb(f); lines=sheet_text.read_lines(rgb); labels=sheet_text.labels(lines)
ppm=14000/1684*72/25.4*1000/200
J=json.load(open(S+"/doorkey-special00.json"))
wall=(cv2.imread(S+"/wall.png",0)>0).astype(np.uint8)
sealed=wall.copy()
H,W=wall.shape
boxes=J["yolo26m-styles"]+J["yolo26m"]+J["yolo26m-styles-window"]+J["yolo26m-window"]
for b in boxes:
    bx0,by0,bx1,by1=[int(v) for v in b]
    m=int(REACH*ppm); x0,y0,x1,y1=max(0,bx0-m),max(0,by0-m),min(W,bx1+m),min(H,by1+m)
    crop=wall[y0:y1,x0:x1]
    k=int(1.6*max(bx1-bx0,by1-by0))|1
    t=int(1.25*ppm)|1   # a wall is thinner than this: a wider band is a room between two walls, not a gap in a wall
    ah=cv2.morphologyEx(crop,cv2.MORPH_CLOSE,np.ones((1,k),np.uint8))&(1-crop)
    ah&=1-cv2.morphologyEx(ah,cv2.MORPH_OPEN,np.ones((t,1),np.uint8))
    av=cv2.morphologyEx(crop,cv2.MORPH_CLOSE,np.ones((k,1),np.uint8))&(1-crop)
    av&=1-cv2.morphologyEx(av,cv2.MORPH_OPEN,np.ones((1,t),np.uint8))
    add=ah|av
    g=int(KEEP*ppm); keep=np.zeros_like(crop); keep[max(0,by0-g-y0):by1+g-y0,max(0,bx0-g-x0):bx1+g-x0]=1
    sealed[y0:y1,x0:x1]|=add&keep
free=(1-sealed).astype(np.uint8)
names=[lb for lb in labels if re.fullmatch(r"[A-Z][A-Za-z /()&'-]{3,40}",lb.text) and not lb.text.isupper()]
out=rgb.copy(); res=defaultdict(list); rng=np.random.default_rng(0)
limit=400*ppm*ppm; seen={}
for lb in names:
    x,y=lb.at
    if not free[y,x]: res[lb.text].append("wall"); continue
    R=int(40*ppm); x0,y0=max(0,x-R),max(0,y-R)
    crop=free[y0:y+R,x0:x+R].copy()
    num,_,_,rect=cv2.floodFill(crop,None,(x-x0,y-y0),2)
    if num>limit or rect[0]==0 or rect[1]==0 or rect[0]+rect[2]>=crop.shape[1] or rect[1]+rect[3]>=crop.shape[0]: res[lb.text].append("LEAK"); continue
    reg=(crop[rect[1]:rect[1]+rect[3],rect[0]:rect[0]+rect[2]]==2).astype(np.uint8)
    cs,_=cv2.findContours(reg,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    area=round(sum(cv2.contourArea(c) for c in cs)/ppm**2,1)
    key=(x0+rect[0],y0+rect[1],rect[2],rect[3])
    shared=key in seen; seen.setdefault(key,lb.text)
    res[lb.text].append(f"{area}*" if shared else area)
    if not shared:
        col=rng.integers(60,255,3)
        sub=out[key[1]:key[1]+key[3],key[0]:key[0]+key[2]]
        sub[reg==1]=(0.5*sub[reg==1]+0.5*col).astype(np.uint8)
for k,v in sorted(res.items()): print(k,v)
Image.fromarray(out).resize((3500,2476)).save(S+"/rooms-uk.jpg",quality=80)
