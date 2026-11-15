# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""What could a question generator (or a lookup shortcut) read from the LICENSE.md tables of the
question-less historic sources? Parses the | file | title | licence | credit | source | tables and
measures how often each field carries an answerable fact (year, creator, place, drawing kind, sheet x of y).

Writes analysis/wild/out/meta_lookup.json and meta_rows.jsonl. Run: uv run stoa/analysis/wild/meta_lookup.py
"""
import json, re, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data/junction-dataset/data"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
SOURCES = ["habs", "finna", "europeana", "wikimedia", "opening_design"]

YEAR = re.compile(r"\b(1[4-9]\d\d|20[0-2]\d)\b")
KIND = {
    "plan": r"\bplan\b|plans\b|grundriss|pohjapiirros|pohjapiirustus|pohja\b|plattegrond|planta|pianta|plano|planol|pôdorys|půdorys|rzut|grundtegning|ritning|alaplan|kerros|floor",
    "elevation": r"elevation|fasad|julkisivu|façade|facade|fațadă|ansicht|aufriss|pohľad|όψη|prospetto|alzado",
    "section": r"section|leikkaus|schnitt|coupe|prierez|sezione|corte|doorsnede|průřez",
    "site": r"site plan|asemapiirros|asemakaava|lageplan|situationsplan|map\b|kartta|karte",
    "detail": r"detail|yksityiskohta",
}
SHEET = re.compile(r"sheet (\d+) of (\d+)", re.I)


def parse(src):
    rows = []
    for line in open(ROOT / src / "LICENSE.md", encoding="utf-8"):
        if not line.startswith("| ") or line.startswith("| file") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split(" | ")]
        if len(parts) < 5:
            continue
        f, title, lic, credit, url = parts[0], parts[1], parts[2], " | ".join(parts[3:-1]), parts[-1]
        rows.append({"source": src, "file": f, "title": title, "licence": lic, "credit": credit, "url": url})
    return rows


def creator(credit):
    c = credit.split(";")[0].strip()
    if re.search(r"unknown|tuntematon|okänd|unbekannt", c, re.I):
        return None
    return c


def main():
    summary = {}
    allrows = []
    for src in SOURCES:
        rows = parse(src)
        files_on_disk = {p.name for p in (ROOT / src).iterdir() if p.is_file() and p.name != "LICENSE.md"} if src != "opening_design" else None
        s = collections.Counter()
        kinds = collections.Counter()
        creators = collections.Counter()
        lic = collections.Counter(r["licence"] for r in rows)
        for r in rows:
            t = r["title"]
            s["rows"] += 1
            s["title_nonempty"] += bool(t)
            s["year_in_title"] += bool(YEAR.search(t))
            s["year_in_title_or_credit"] += bool(YEAR.search(t + " " + r["credit"]))
            s["source_url"] += r["url"].startswith("http")
            cr = creator(r["credit"])
            s["named_creator"] += bool(cr)
            if cr:
                creators[cr] += 1
            k = [name for name, rx in KIND.items() if re.search(rx, t, re.I)]
            kinds[k[0] if k else "none"] += 1
            s["kind_in_title"] += bool(k)
            m = SHEET.search(t)
            s["sheet_x_of_y"] += bool(m)
            r["year"] = (YEAR.search(t) or [None])[0] if YEAR.search(t) else None
            r["kind_from_title"] = k[0] if k else None
            r["creator"] = cr
            allrows.append(r)
        titles = collections.Counter(r["title"] for r in rows if r["title"])
        summary[src] = {
            **dict(s),
            "files_on_disk": len(files_on_disk) if files_on_disk is not None else None,
            "rows_missing_on_disk": (sum(1 for r in rows if r["file"] not in files_on_disk) if files_on_disk is not None else None),
            "disk_files_missing_in_table": (len(files_on_disk - {r["file"] for r in rows}) if files_on_disk is not None else None),
            "distinct_titles": len(titles),
            "titles_shared_by_2plus_files": sum(1 for v in titles.values() if v > 1),
            "kind_from_title": dict(kinds),
            "licences": dict(lic.most_common()),
            "distinct_creators": len(creators),
            "top_creators": creators.most_common(8),
        }
    json.dump(summary, open(OUT / "meta_lookup.json", "w"), indent=1, ensure_ascii=False)
    with open(OUT / "meta_rows.jsonl", "w") as f:
        for r in allrows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for src, v in summary.items():
        print(src, {k: v[k] for k in ["rows", "title_nonempty", "year_in_title", "named_creator", "kind_in_title", "sheet_x_of_y", "distinct_titles", "rows_missing_on_disk", "disk_files_missing_in_table"]})


if __name__ == "__main__":
    main()
