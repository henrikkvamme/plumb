"""CubiCasa: image sizes, exact and near duplicates (dHash 16x16), subset sizes."""
import sys, os, hashlib, collections, json
from PIL import Image
import numpy as np
root = sys.argv[1]; d = os.path.join(root, "data", "cubicasa5k")
files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
H = []; md5 = collections.defaultdict(list); W = []
for f in files:
    p = os.path.join(d, f)
    md5[hashlib.md5(open(p, "rb").read()).hexdigest()].append(f)
    im = Image.open(p); W.append(im.size)
    g = np.asarray(im.convert("L").resize((17, 16), Image.LANCZOS), dtype=np.int16)
    H.append((g[:, 1:] > g[:, :-1]).flatten())
H = np.array(H, dtype=np.uint8)
ws = sorted(w for w, h in W); hs = sorted(h for w, h in W)
print("n", len(files), "width p10/p50/p90/max", ws[len(ws)//10], ws[len(ws)//2], ws[len(ws)*9//10], ws[-1], "height p50", hs[len(hs)//2])
print("subsets", dict(collections.Counter(f.rsplit("-", 1)[0] for f in files)))
print("exact md5 duplicate sets", sum(1 for v in md5.values() if len(v) > 1))
Hf = H.astype(np.float32); n = len(files)
parent = list(range(n))
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
cnt = collections.Counter()
for i in range(0, n, 500):
    a = Hf[i:i+500]
    dist = a.sum(1)[:, None] + Hf.sum(1)[None, :] - 2 * a @ Hf.T
    for thr in (8, 16, 24, 32): cnt[thr] += int(((dist <= thr).sum() - len(a)))
    ii, jj = np.where(dist <= 16)
    for x, y in zip(ii + i, jj):
        if x < y: parent[find(x)] = find(y)
print("ordered near pairs by Hamming threshold (of 256 bits), each pair counted twice:", dict(cnt))
comp = collections.Counter(find(i) for i in range(n))
sizes = sorted((c for c in comp.values() if c > 1), reverse=True)
print("clusters at <=16 bits:", len(comp), "multi-member clusters", len(sizes), "drawings in them", sum(sizes), "top", sizes[:10])
ex = [[files[i] for i in range(n) if find(i) == r] for r, c in comp.items() if c > 1][:5]
print("examples", ex)
json.dump({files[i]: files[find(i)] for i in range(n)}, open(sys.argv[2], "w"))
