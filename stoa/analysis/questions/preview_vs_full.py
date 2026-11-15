# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Topic 2: what changed between the preview question file and the full question file.

Compares (path, question) keys, answers, templates, paths and the drawing files themselves.
Writes analysis/questions/out/preview_vs_full.json.

Run: uv run preview_vs_full.py
"""

from __future__ import annotations

import hashlib
import os
from collections import Counter

from qcommon import FULL, OUT_DIR, PREVIEW, STOA, annotate, answer_key, load, write_json


def model_of(path: str) -> str:
    name = path.split("/")[-1]
    return name.split("_plan-")[0].rsplit(".", 1)[0]


def file_hashes(root) -> dict[str, str]:
    out = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            h = hashlib.sha1()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[os.path.relpath(p, root)] = h.hexdigest()
    return out


def main() -> None:
    F = annotate(load(FULL))
    P = annotate(load(PREVIEW))
    fk = {(r["path"], r["question"]): r for r in F}
    pk = {(r["path"], r["question"]): r for r in P}
    fpaths = {r["path"] for r in F}
    ppaths = {r["path"] for r in P}
    by_q: dict[str, list] = {}
    for r in F:
        by_q.setdefault(r["question"], []).append(r)

    res: dict = {
        "preview_rows": len(P),
        "full_rows": len(F),
        "preview_rows_per_source": dict(Counter(r["_src"] for r in P)),
        "preview_drawings": len(ppaths),
        "preview_drawings_in_full_questions": len(ppaths & fpaths),
        "duplicate_keys_preview": sum(v > 1 for v in Counter((r["path"], r["question"]) for r in P).values()),
        "duplicate_keys_full": sum(v > 1 for v in Counter((r["path"], r["question"]) for r in F).values()),
    }

    matched = [(r, fk[(r["path"], r["question"])]) for r in P if (r["path"], r["question"]) in fk]
    changed = [
        (a, b)
        for a, b in matched
        if answer_key(a) != answer_key(b) or a["type"] != b["type"] or a["unit"] != b["unit"]
    ]
    res["matched_rows"] = len(matched)
    res["matched_rows_answer_type_or_unit_changed"] = len(changed)
    res["changed_examples"] = [
        {"path": a["path"], "question": a["question"], "preview": a["answer"], "full": b["answer"]}
        for a, b in changed[:10]
    ]

    unmatched = [r for r in P if (r["path"], r["question"]) not in fk]
    kinds = Counter()
    examples: dict[str, list] = {}
    for r in unmatched:
        cands = [f for f in by_q.get(r["question"], []) if model_of(f["path"]) == model_of(r["path"])]
        if r["path"] not in fpaths:
            where = "path has no questions in full"
        else:
            where = "path kept, this question moved away"
        if not cands:
            kind = where + "; question text gone"
        elif any(answer_key(f) == answer_key(r) for f in cands):
            kind = where + "; same question and answer now on another file of the same model"
        else:
            kind = where + "; question on another file with another answer"
        if r["path"].endswith(".ifc"):
            kind = "from .ifc: " + kind
        else:
            kind = "from plan PDF: " + kind
        kinds[kind] += 1
        ex = examples.setdefault(kind, [])
        if len(ex) < 5:
            ex.append(
                {
                    "preview_path": r["path"],
                    "question": r["question"],
                    "answer": r["answer"],
                    "full_paths": sorted({f["path"] for f in cands})[:4],
                }
            )
    res["unmatched_rows"] = len(unmatched)
    res["unmatched_by_source"] = dict(Counter(r["_src"] for r in unmatched))
    res["unmatched_by_kind"] = dict(kinds)
    res["unmatched_examples"] = examples
    res["unmatched_by_preview_path"] = dict(Counter(r["path"] for r in unmatched))
    res["unmatched_templates_absent_from_full"] = sorted(
        {r["_tpl"] for r in unmatched} - {r["_tpl"] for r in F}
    )

    # Rows in full on preview drawings that the preview did not have.
    added = [r for r in F if r["path"] in ppaths and (r["path"], r["question"]) not in pk]
    res["full_rows_on_preview_drawings_not_in_preview"] = len(added)
    res["added_examples"] = [
        {"path": r["path"], "question": r["question"], "answer": r["answer"]} for r in added[:10]
    ]

    # Where model-wide and storey questions live in each file.
    def placement(rows):
        im = [r for r in rows if r["_src"] == "ifc_models"]
        return {
            "rows": len(im),
            "on_ifc": sum(r["path"].endswith(".ifc") for r in im),
            "on_pdf": sum(r["path"].endswith(".pdf") for r in im),
            "model_wide_rows": sum(any(k == "model" for k, _ in r["_slots"]) for r in im),
            "model_wide_on_ifc": sum(
                any(k == "model" for k, _ in r["_slots"]) and r["path"].endswith(".ifc") for r in im
            ),
        }

    res["ifc_models_placement"] = {"preview": placement(P), "full": placement(F)}
    # Which plan sheet carries the model-wide questions (they cannot be read off one sheet).
    import re as _re

    mw = [r for r in F if r["_src"] == "ifc_models" and any(k == "model" for k, _ in r["_slots"])]
    res["model_wide_question_file"] = dict(
        Counter(
            ("ifc" if r["path"].endswith(".ifc") else "plan-" + _re.search(r"_plan-(\d+)", r["path"]).group(1))
            for r in mw
        )
    )

    # Templates in preview that do not exist in full, and the other way round, per source.
    ptpl = {(r["_src"], r["_tpl"]) for r in P}
    ftpl = {(r["_src"], r["_tpl"]) for r in F}
    res["templates_only_in_preview"] = len(ptpl - ftpl)
    res["templates_only_in_full"] = Counter(s for s, _ in ftpl - ptpl)
    res["ifc_models_languages"] = {
        "preview": dict(Counter(r["_lang"] for r in P if r["_src"] == "ifc_models")),
        "full": dict(Counter(r["_lang"] for r in F if r["_src"] == "ifc_models")),
        "full_rows_on_templates_absent_from_preview": dict(
            Counter(r["_lang"] for r in F if r["_src"] == "ifc_models" and (r["_src"], r["_tpl"]) not in ptpl)
        ),
    }
    res["ifc_models_projects"] = {
        "preview": len({r["path"].split("/")[-1].split("_")[0] for r in P if r["_src"] == "ifc_models"}),
        "full": len({r["path"].split("/")[-1].split("_")[0] for r in F if r["_src"] == "ifc_models"}),
    }

    # Drawing files: are the preview files byte-identical to the full files?
    pf = file_hashes(STOA / "data" / "junction-dataset-preview" / "data")
    ff = file_hashes(STOA / "data" / "junction-dataset" / "data")
    same = sum(1 for p, h in pf.items() if ff.get(p) == h)
    diff = [p for p, h in pf.items() if p in ff and ff[p] != h]
    missing = [p for p in pf if p not in ff]
    res["preview_files"] = len(pf)
    res["preview_files_identical_in_full"] = same
    res["preview_files_different_in_full"] = diff
    res["preview_files_missing_in_full"] = missing
    write_json(OUT_DIR / "preview_vs_full.json", res)
    print("unmatched", len(unmatched), dict(kinds))
    print("files identical", same, "of", len(pf), "different", len(diff), "missing", len(missing))


if __name__ == "__main__":
    main()
