# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""Inventory of data/opening_design: projects, formats, PDF pages, text layer, sheet kinds.

Writes analysis/wild/out/od_inventory.json and od_pdfs.jsonl (one row per PDF).
Run: uv run stoa/analysis/wild/od_inventory.py
"""
import json, re, collections
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[2] / "data/junction-dataset"
OD = ROOT / "data/opening_design"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

KINDS = [
    ("schedule", r"schedul|\bA-?8\d\d|\bA700\b"),
    ("plan", r"plan|layout|\bA-?1\d\d|\bA-?2\d\d|\bA1\d\d"),
    ("elevation", r"elevat|\bA-?3\d\d|\bA2\d\d"),
    ("section", r"section|\bA-?4\d\d|\bA3\d\d"),
    ("detail", r"detail|\bA-?5\d\d|\bA-?6\d\d"),
    ("cover", r"cover|title|index|\bG-?\d|\bT-?\d|\bA-?0\d\d"),
    ("structural", r"^S-?\d|struct|framing|foundation"),
    ("mep", r"^[MEP]-?\d|mechan|electr|plumb"),
    ("site", r"site|^C-?\d|civil"),
]


def kind(name: str) -> str:
    n = name.lower()
    for k, rx in KINDS:
        if re.search(rx, n, re.I):
            return k
    return "other"


def main():
    qpaths = collections.Counter()
    for line in open(ROOT / "questions.jsonl"):
        r = json.loads(line)
        if r["path"].startswith("data/opening_design/"):
            qpaths[r["path"]] += 1
    files = [p for p in OD.rglob("*") if p.is_file() and p.name != "LICENSE.md"]
    per_project = collections.defaultdict(collections.Counter)
    rows = []
    for p in sorted(files):
        rel = p.relative_to(OD)
        proj = rel.parts[0]
        ext = p.suffix.lower().lstrip(".")
        per_project[proj][ext] += 1
        if ext != "pdf":
            continue
        row = {"path": str(rel), "project": proj, "bytes": p.stat().st_size,
               "kind_from_name": kind(p.stem), "questions": qpaths.get(f"data/opening_design/{rel}", 0)}
        try:
            d = fitz.open(p)
            row["pages"] = d.page_count
            pg = d[0]
            row["size_in"] = [round(pg.rect.width / 72, 1), round(pg.rect.height / 72, 1)]
            txt = "".join(d[i].get_text() for i in range(min(d.page_count, 3)))
            row["text_chars_first3"] = len(txt)
            row["n_images_p1"] = len(pg.get_images())
            row["has_scale_text"] = bool(re.search(r"\d+/\d+\"\s*=\s*1'-0\"|SCALE", txt))
            row["has_ft_in"] = bool(re.search(r"\d+'-\s?\d+", txt))
            row["has_door_sched"] = bool(re.search(r"DOOR SCHEDULE", txt, re.I))
            row["has_window_sched"] = bool(re.search(r"WINDOW SCHEDULE", txt, re.I))
            row["has_finish_sched"] = bool(re.search(r"FINISH", txt, re.I) and re.search(r"SCHEDULE", txt, re.I))
            row["has_area_sf"] = bool(re.search(r"\d\s?(SF|SQ\.? ?FT)", txt))
            d.close()
        except Exception as e:  # noqa: BLE001
            row["error"] = str(e)[:100]
        rows.append(row)
    with open(OUT / "od_pdfs.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = {
        "n_files": len(files),
        "n_projects": len(per_project),
        "ext_total": dict(sum((c for c in per_project.values()), collections.Counter())),
        "per_project": {k: dict(v) for k, v in sorted(per_project.items())},
        "n_pdfs": len(rows),
        "pdf_pages_total": sum(r.get("pages", 0) for r in rows),
        "pdf_multi_page": sum(1 for r in rows if r.get("pages", 0) > 1),
        "pdf_no_text": sum(1 for r in rows if r.get("text_chars_first3", 0) < 50),
        "kind_from_name": dict(collections.Counter(r["kind_from_name"] for r in rows)),
        "sheet_sizes": dict(collections.Counter(str(r.get("size_in")) for r in rows).most_common(12)),
        "pdfs_with_door_sched": sum(r.get("has_door_sched", False) for r in rows),
        "pdfs_with_window_sched": sum(r.get("has_window_sched", False) for r in rows),
        "pdfs_with_finish_sched": sum(r.get("has_finish_sched", False) for r in rows),
        "pdfs_with_area_sf": sum(r.get("has_area_sf", False) for r in rows),
        "pdfs_with_ft_in": sum(r.get("has_ft_in", False) for r in rows),
        "pdfs_with_questions": sum(1 for r in rows if r["questions"]),
        "questions_per_pdf": {k: v for k, v in qpaths.items()},
        "errors": [r for r in rows if "error" in r][:10],
    }
    json.dump(summary, open(OUT / "od_inventory.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_project"}, indent=None)[:3000])


if __name__ == "__main__":
    main()
