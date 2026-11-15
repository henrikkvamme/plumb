# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""opening_design: how many sheets exist in more than one revision (same project, same sheet number),
and which PDFs have no text layer. Reads analysis/wild/out/od_pdfs.jsonl (run od_inventory.py first).

Writes analysis/wild/out/od_revisions.json. Run: uv run stoa/analysis/wild/od_revisions.py
"""
import json, re, collections
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
rows = [json.loads(l) for l in open(OUT / "od_pdfs.jsonl")]
CODE = re.compile(r"\b([AGSCMEPT])-?(\d{3})(\.[A-Z])?\b")
groups = collections.defaultdict(list)
for r in rows:
    name = r["path"].split("/")[-1]
    m = CODE.search(name)
    if m and r.get("pages", 0) == 1:
        groups[(r["project"], m.group(1) + m.group(2) + (m.group(3) or ""))].append(r["path"])
multi = {f"{k[0]}:{k[1]}": v for k, v in groups.items() if len(v) > 1}
no_text = [r["path"] for r in rows if r.get("text_chars_first3", 0) < 50]
res = {
    "single_page_pdfs_with_sheet_code": sum(len(v) for v in groups.values()),
    "distinct_project_sheet_codes": len(groups),
    "codes_with_more_than_one_file": len(multi),
    "files_in_multi_revision_groups": sum(len(v) for v in multi.values()),
    "max_revisions": max((len(v) for v in multi.values()), default=0),
    "examples": dict(list(sorted(multi.items(), key=lambda kv: -len(kv[1])))[:8]),
    "pdfs_without_text_layer": len(no_text),
    "no_text_by_project": dict(collections.Counter(p.split("/")[0] for p in no_text)),
    "no_text_examples": no_text[:20],
    "pages_hist": dict(collections.Counter(min(r.get("pages", 0), 20) for r in rows)),
    "pdfs_in_current_set_folders": sum(1 for r in rows if re.search(r"Current Set|Most Current", r["path"])),
    "pdfs_in_transfer_folders": sum(1 for r in rows if "/Transfer/" in r["path"]),
}
json.dump(res, open(OUT / "od_revisions.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("examples", "no_text_examples")}))
