"""Red-team pool sizes: split_v0 vs the public CubiCasa5K split, dropped-template pool, zero-answer pool."""
import json, collections, re, os
A = os.path.dirname(os.path.abspath(__file__)) + "/.."
pub = json.load(open(A + "/cubicasa/out/public_ids.json"))
s = json.load(open(A + "/questions/split_v0.json"))
g = s["groups"]
it = list(g.items())[:2] if isinstance(g, dict) else g[:2]
print("groups sample", str(it)[:200])
def split_of(key):
    v = g.get(key) if isinstance(g, dict) else None
    return v if isinstance(v, str) else (v.get("split") if isinstance(v, dict) else None)
tab = collections.Counter()
for name, d in pub.items():
    if not d["in_stoa"]: continue
    pid = name.rsplit("-", 1)[1]
    tab[(split_of("cubicasa5k:" + pid), d["split"])] += 1
print("split_v0 x public CubiCasa5K split (plans):", dict(sorted(tab.items(), key=str)))
rows = [json.loads(l) for l in open(A + "/../data/junction-dataset/questions.jsonl")]
cc = collections.defaultdict(set); sw = collections.defaultdict(set)
KEY = [("windows","window"),("doors","door"),("floors","floors|storeys|levels"),("toilet","toilet bowl"),("sinks","sink"),("shower","shower"),("bedrooms","bedroom"),("kitchens","kitchen"),("bathrooms","bathroom"),("wc_rooms","WC rooms"),("saunas","sauna"),("balconies","balcon")]
for r in rows:
    src = r["path"].split("/")[1]; q = r["question"]
    if src == "cubicasa5k" and q.startswith(("How", "What")):
        for k, rx in KEY:
            if re.search(rx, q): cc[k].add(r["path"]); break
        else: cc["?" + q[:40]].add(r["path"])
    if src == "swiss_dwellings" and q.startswith("How many"):
        for k in ("bathtub", "shower", "toilet", "washbasin"):
            if k in q: sw[k].add(r["path"])
n = 4787
pv = {("cubicasa5k/" + k + ".png") for k, d in pub.items() if d["in_stoa"] and d["split"] != "train"}
print("cubicasa plans where the template is NOT asked (dropped as ambiguous or absent): all | in public val+test")
for k, v in sorted(cc.items(), key=lambda kv: len(kv[1])):
    miss_pv = sum(1 for p in pv if ("data/" + p) not in v)
    print(f"  {k:10s} asked {len(v):5d} dropped {n-len(v):5d} | dropped in val+test {miss_pv}")
print("swiss floors where the fixture question is absent (reference would be 0):", {k: 1040 - len(v) for k, v in sw.items()})
