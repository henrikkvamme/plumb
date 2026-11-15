# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Question coverage per source: files on disk, drawings (same stem = same drawing), drawings with at least one
question, in the full set and in the preview. Tests the README claim "questions for roughly 40% of them".

Writes analysis/wild/out/coverage.json. Run: uv run stoa/analysis/wild/coverage.py
"""
import json, collections
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "data"
OUT = Path(__file__).resolve().parent / "out"


def scan(ds):
    root = BASE / ds
    q = collections.defaultdict(set)
    qn = collections.Counter()
    for line in open(root / "questions.jsonl"):
        r = json.loads(line)
        src = r["path"].split("/")[1]
        q[src].add(r["path"].rsplit(".", 1)[0])
        qn[src] += 1
    res = {}
    tot_files = tot_draw = tot_qdraw = 0
    for sd in sorted((root / "data").iterdir()):
        if not sd.is_dir():
            continue
        files = [p for p in sd.rglob("*") if p.is_file() and p.name != "LICENSE.md"]
        stems = {str(p.relative_to(root)).rsplit(".", 1)[0] for p in files}
        exts = collections.Counter(p.suffix.lower() for p in files)
        qd = q.get(sd.name, set())
        res[sd.name] = {"files": len(files), "drawings": len(stems), "drawings_with_q": len(qd & stems),
                        "q_stems_not_on_disk": len(qd - stems), "questions": qn.get(sd.name, 0),
                        "exts": dict(exts.most_common(6))}
        tot_files += len(files)
        tot_draw += len(stems)
        tot_qdraw += len(qd & stems)
    res["_total"] = {"files": tot_files, "drawings": tot_draw, "drawings_with_q": tot_qdraw,
                     "share_drawings_with_q": round(tot_qdraw / tot_draw, 3)}
    return res


out = {"full": scan("junction-dataset"), "preview": scan("junction-dataset-preview")}
json.dump(out, open(OUT / "coverage.json", "w"), indent=1)
for ds, r in out.items():
    print(ds)
    for k, v in r.items():
        print(" ", k, {kk: vv for kk, vv in v.items() if kk != "exts"})
