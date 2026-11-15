# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Summarise out/inventory.jsonl (from 02_inventory.py) with question coverage per model.

Writes out/inventory_table.md and out/inventory_summary.json.
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
OUT = HERE / "out"


def main():
    inv = [json.loads(l) for l in open(OUT / "inventory.jsonl")]
    qs = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_' in l]
    qcount = collections.Counter()
    for r in qs:
        name = r["path"].split("/")[-1]
        src = r["path"].split("/")[1]
        if src == "ifc_models" and name.endswith(".pdf"):
            # model = longest IFC stem that prefixes the PDF name
            stems = [i["file"].split("/")[1][:-4] for i in inv if i["file"].startswith("ifc_models/")]
            m = max((s for s in stems if name.startswith(s + "_")), key=len)
            qcount[f"ifc_models/{m}.ifc|pdf"] += 1
        else:
            qcount[f"{src}/{name}|ifc"] += 1
    sheets = collections.Counter()
    for p in (DS / "data" / "ifc_models").glob("*.pdf"):
        stems = [i["file"].split("/")[1][:-4] for i in inv if i["file"].startswith("ifc_models/")]
        m = max((s for s in stems if p.name.startswith(s + "_")), key=len)
        sheets[f"ifc_models/{m}.ifc"] += 1
    rows = []
    for i in inv:
        if "error" in i:
            rows.append(f"| {i['file']} | ERROR | | | | | | | | |")
            continue
        c = i["counts"]
        walls = (c.get("IfcWall") or 0)
        app = (i["applications"] or [i.get("originating_system") or "?"])[0][:38]
        rows.append(
            f"| {i['file'].split('/')[1][:48]} | {i['schema']} | {i['bytes']/1e6:.1f} | {app} | {len(i['storeys'])} | "
            f"{c.get('IfcSpace')} | {i['spaces_with_area_qto']} | {','.join(k for k in i['qto_sets'] if 'Qto_' in k or k=='BaseQuantities')[:40] or '-'} | "
            f"{walls}/{c.get('IfcSlab')}/{c.get('IfcDoor')}/{c.get('IfcWindow')} | {sheets.get(i['file'],0)} | "
            f"{qcount.get(i['file']+'|pdf',0)}+{qcount.get(i['file']+'|ifc',0)} | {i['open_s']} | {i['peak_rss_mb']} |"
        )
    hdr = "| file | schema | MB | application | storeys | IfcSpace | spaces w/ area Qto | Qto sets | wall/slab/door/window | sheets | questions pdf+ifc | open s | peak RSS MB |\n|" + "---|" * 13
    non_res = [r for r, i in zip(rows, inv) if "resbim" not in i["file"]]
    (OUT / "inventory_table.md").write_text(hdr + "\n" + "\n".join(non_res) + "\n")
    res = [i for i in inv if "resbim" in i["file"] and "error" not in i]
    ok = [i for i in inv if "error" not in i]
    summ = {
        "n_files": len(inv), "errors": [i["file"] for i in inv if "error" in i],
        "schemas": dict(collections.Counter(i["schema"] for i in ok)),
        "schemas_non_resbim": dict(collections.Counter(i["schema"] for i in ok if "resbim" not in i["file"])),
        "apps_non_resbim": dict(collections.Counter((i["applications"] or ["?"])[0].split(" ")[0] for i in ok if "resbim" not in i["file"])),
        "with_ifcspace_non_resbim": sum(1 for i in ok if "resbim" not in i["file"] and (i["counts"]["IfcSpace"] or 0) > 0),
        "non_resbim": sum(1 for i in ok if "resbim" not in i["file"]),
        "with_qto_any_non_resbim": sum(1 for i in ok if "resbim" not in i["file"] and any(("Qto_" in k or k == "BaseQuantities") for k in i["qto_sets"])),
        "resbim": {
            "n": len(res), "apps": dict(collections.Counter((i["applications"] or [i.get("originating_system") or "?"])[0] for i in res)),
            "schemas": dict(collections.Counter(i["schema"] for i in res)),
            "storeys": dict(collections.Counter(len(i["storeys"]) for i in res)),
            "spaces": dict(collections.Counter(i["counts"]["IfcSpace"] for i in res).most_common(10)),
            "qto_any": sum(1 for i in res if i["qto_sets"]),
            "max_mb": max(i["bytes"] for i in res) / 1e6,
            "example_counts": res[0]["counts"] if res else None,
            "n_with_questions": sum(1 for i in res if qcount.get(i["file"] + "|ifc", 0) + qcount.get(i["file"] + "|pdf", 0)),
        },
        "models_with_questions": sorted(k for k in qcount),
        "ifc_models_without_questions_non_resbim": sorted(i["file"] for i in ok if i["file"].startswith("ifc_models/") and "resbim" not in i["file"] and not (qcount.get(i["file"] + "|pdf") or qcount.get(i["file"] + "|ifc"))),
        "max_open": max(((i["open_s"], i["file"]) for i in ok)),
        "max_rss": max(((i["peak_rss_mb"], i["file"]) for i in ok)),
    }
    json.dump(summ, open(OUT / "inventory_summary.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summ.items() if k != "models_with_questions"}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
