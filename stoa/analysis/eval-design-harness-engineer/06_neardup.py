"""Near-duplicate drawings inside cubicasa5k and swiss_dwellings PNGs: 256-bit dHash, clusters at Hamming <= 10 (same aspect bucket)."""
import os, sys, collections, hashlib
from multiprocessing import Pool
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ROOT = "./stoa/data/junction-dataset/data"
def h(p):
    try:
        im = Image.open(p).convert("L")
        w, hh = im.size
        im = im.resize((17, 16), Image.LANCZOS)
        px = list(im.getdata()); bits = 0
        for y in range(16):
            for x in range(16):
                bits = (bits << 1) | (px[y * 17 + x] > px[y * 17 + x + 1])
        md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
        return (p, bits, w, hh, md5)
    except Exception as e:
        return (p, None, 0, 0, str(e))
if __name__ == "__main__":
    for s in ["cubicasa5k", "swiss_dwellings"]:
        fs = sorted(f"{ROOT}/{s}/{f}" for f in os.listdir(f"{ROOT}/{s}") if f.endswith(".png"))
        with Pool(8) as pool: res = pool.map(h, fs, chunksize=64)
        ok = [r for r in res if r[1] is not None]
        md = collections.Counter(r[4] for r in ok)
        ws = sorted(r[2] for r in ok)
        # union-find over pairs with hamming <= T
        par = list(range(len(ok)))
        def find(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        hs = [r[1] for r in ok]; n = len(ok); T = 10; pairs = 0
        for i in range(n):
            hi = hs[i]
            for j in range(i + 1, n):
                if (hi ^ hs[j]).bit_count() <= T:
                    pairs += 1; par[find(i)] = find(j)
        cl = collections.Counter(find(i) for i in range(n))
        big = sorted((c for c in cl.values() if c > 1), reverse=True)
        print(s, "images", n, "errors", len(res) - n, "byte-identical extra", sum(c - 1 for c in md.values()), "width p10/med/p90", ws[n // 10], ws[n // 2], ws[9 * n // 10],
              "| near-dup pairs", pairs, "clusters>1", len(big), "images in clusters", sum(big), "largest", big[:5])
        ex = [k for k, c in cl.items() if c > 1][:3]
        for k in ex: print("  example", [os.path.basename(ok[i][0]) for i in range(n) if find(i) == k][:4])
