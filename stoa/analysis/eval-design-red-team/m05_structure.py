"""Structure: languages, families, pairs, groups. Compact output."""
import collections
from common import *
it = items()
print("rows", len(it), "pairs(unique items)", len(set(x["pair"] for x in it)))
bs = collections.defaultdict(list)
for x in it: bs[x["source"]].append(x)
for s, xs in sorted(bs.items()):
    langs = collections.Counter(x["lang"] for x in xs)
    fams = collections.Counter(x["family"] for x in xs)
    tm = collections.Counter(x["template"] for x in xs)
    files = set(x["path"] for x in xs); groups = set(x["group"] for x in xs)
    unp = sum(1 for x in xs if x["lang"]!="en" and not x["has_pair"])
    en_only = sum(1 for x in xs if x["lang"]=="en" and not x["has_pair"])
    print(f"== {s}: rows={len(xs)} items={len(set(x['pair'] for x in xs))} files={len(files)} groups={len(groups)} templates={len(tm)} families={len(fams)} nonEN_unpaired={unp} EN_without_pair={en_only}")
    print("   langs", dict(langs.most_common()))
    if s in ("cubicasa5k","swiss_dwellings","ifc_models"):
        for f, n in fams.most_common(40): 
            typ = collections.Counter(x["unit"] for x in xs if x["family"]==f).most_common(1)[0][0]
            print(f"   {n}\t{typ}\t{f[:100]}")
