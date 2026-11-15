# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Template census for cubicasa5k questions.

Writes out/templates.json: per template the count of questions, the answer distribution,
the mode-guess accuracy, the English/Finnish pair agreement, and per-drawing template presence.
Also writes out/images.json with image size and mode stats per style group.
"""
import json
import collections
import pathlib
import re
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
DS = ROOT / "data/junction-dataset"
OUT = pathlib.Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

# Template key: an English template and its Finnish twin share a short key.
KEYS = [
    ("doors", "How many doors", "Kuinka monta ovea"),
    ("windows", "How many windows", "Kuinka monta ikkunaa"),
    ("bedrooms", "How many bedrooms", "Kuinka monta makuuhuonetta"),
    ("saunas", "How many saunas", "Kuinka monta saunaa"),
    ("balconies", "How many balconies", "Kuinka monta parveketta"),
    ("toilets", "How many toilet bowls", "Kuinka monta WC-istuinta"),
    ("sinks", "How many sinks", "Kuinka monta pesu- ja tiskiallasta"),
    ("showers_tubs", "How many showers and bathtubs", "Kuinka monta suihkua ja kylpyammetta"),
    ("floors", "How many floors", "Kuinka monta kerrosta"),
    ("kitchens", "How many kitchens", "Kuinka monta keittiötä"),
    ("bathrooms", "How many bathrooms", "Kuinka monta kylpy- tai pesuhuonetta"),
    ("wc_rooms", "How many separate WC rooms", "Kuinka monta erillistä WC-tilaa"),
]


def main():
    rows = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/cubicasa5k/' in l]
    qtexts = collections.Counter(r["question"] for r in rows)
    files = sorted({r["path"] for r in rows})
    all_png = sorted(p.name for p in (DS / "data/cubicasa5k").glob("*.png"))
    per_template = collections.defaultdict(list)  # template text -> answers
    by_file = collections.defaultdict(dict)  # file -> template text -> answer
    for r in rows:
        per_template[r["question"]].append(r["answer"])
        by_file[r["path"]][r["question"]] = r["answer"]

    def key_of(q):
        for k, en, fi in KEYS:
            if q.startswith(en):
                return k, "en"
            if q.startswith(fi):
                return k, "fi"
        return None, None

    templates = []
    for q, answers in sorted(per_template.items(), key=lambda kv: -len(kv[1])):
        c = collections.Counter(answers)
        mode, mode_n = c.most_common(1)[0]
        k, lang = key_of(q)
        templates.append({
            "key": k, "lang": lang, "question": q, "n": len(answers),
            "mode": mode, "mode_acc": round(mode_n / len(answers), 4),
            "zero_share": round(c.get(0, 0) / len(answers), 4),
            "min": min(answers), "max": max(answers),
            "mean": round(sum(answers) / len(answers), 3),
            "dist": dict(sorted(c.items())),
        })
    # pair agreement
    pair = {}
    for k, en, fi in KEYS:
        both = agree = only_en = only_fi = 0
        dis = []
        for f, qa in by_file.items():
            a_en = [v for q, v in qa.items() if q.startswith(en)]
            a_fi = [v for q, v in qa.items() if q.startswith(fi)]
            if a_en and a_fi:
                both += 1
                if a_en[0] == a_fi[0]:
                    agree += 1
                else:
                    dis.append((f, a_en[0], a_fi[0]))
            elif a_en:
                only_en += 1
            elif a_fi:
                only_fi += 1
        pair[k] = {"both": both, "agree": agree, "only_en": only_en, "only_fi": only_fi, "disagree_examples": dis[:5]}
    # per-file presence (by key, English)
    presence = {}
    for f, qa in by_file.items():
        presence[f] = {}
        for q, v in qa.items():
            k, lang = key_of(q)
            if lang == "en":
                presence[f][k] = v
    keyed_presence = collections.Counter(k for f in presence for k in presence[f])
    # mode accuracy overall
    total = sum(t["n"] for t in templates)
    mode_hits = sum(t["mode_acc"] * t["n"] for t in templates)
    groups = collections.Counter(f.split("/")[-1].rsplit("-", 1)[0] for f in files)
    summary = {
        "rows": len(rows), "distinct_questions": len(qtexts), "files_with_questions": len(files),
        "png_files": len(all_png), "png_without_questions": sorted(set(all_png) - {f.split('/')[-1] for f in files}),
        "groups_with_questions": dict(groups),
        "groups_all_png": dict(collections.Counter(p.rsplit('-', 1)[0] for p in all_png)),
        "mode_guess_overall": round(mode_hits / total, 4),
        "files_per_key": dict(keyed_presence),
        "questions_per_file": dict(collections.Counter(len(v) for v in by_file.values())),
    }
    json.dump({"summary": summary, "templates": templates, "pairs": pair}, open(OUT / "templates.json", "w"), indent=1, ensure_ascii=False)
    json.dump(presence, open(OUT / "presence.json", "w"))

    # images
    stats = collections.defaultdict(lambda: {"n": 0, "modes": collections.Counter(), "w": [], "h": [], "bytes": [], "dpi": collections.Counter()})
    for p in sorted((DS / "data/cubicasa5k").glob("*.png")):
        g = p.name.rsplit("-", 1)[0]
        im = Image.open(p)
        s = stats[g]
        s["n"] += 1
        s["modes"][im.mode] += 1
        s["w"].append(im.width)
        s["h"].append(im.height)
        s["bytes"].append(p.stat().st_size)
        s["dpi"][str(im.info.get("dpi"))] += 1
    sizes = {}
    for p in sorted((DS / "data/cubicasa5k").glob("*.png")):
        pass
    img_out = {}
    for g, s in stats.items():
        def q(a):
            a = sorted(a)
            return {"min": a[0], "p10": a[len(a) // 10], "median": a[len(a) // 2], "p90": a[len(a) * 9 // 10], "max": a[-1]}
        img_out[g] = {"n": s["n"], "modes": dict(s["modes"]), "width": q(s["w"]), "height": q(s["h"]), "bytes": q(s["bytes"]), "dpi": dict(s["dpi"].most_common(5))}
    json.dump(img_out, open(OUT / "images.json", "w"), indent=1)
    print("ok", len(rows), len(files), len(templates))


if __name__ == "__main__":
    main()
