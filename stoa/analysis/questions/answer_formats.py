# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Topic 5: answer formats. Types, units, numeric precision, value ranges, text answer phrasing.

Writes analysis/questions/out/answer_formats.json.
Run: uv run answer_formats.py
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from qcommon import FULL, OUT_DIR, annotate, load, write_json

ABSTAIN = re.compile(
    r"not (explicitly )?(available|defined|specified|provided|present|stored|found)|cannot be|"
    r"no (information|data)|unknown|not possible|unable to|information not",
    re.I,
)
UNIT_IN_Q = [
    ("m2", re.compile(r"m²|m2\b|sq ?m")),
    ("m3", re.compile(r"m³|m3\b")),
    ("m", re.compile(r"\bmetres\b|\bmeters?\b|\bMetern\b|\bmeter\b|\bmetri\b")),
    ("ft2", re.compile(r"\bSF\b|sq ?ft|ft²|area room|total area", re.I)),
]


def decimals(x) -> int:
    s = repr(float(x))
    if "e" in s:
        return -1
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def main() -> None:
    rows = annotate(load(FULL))
    res = {}
    res["type_values"] = dict(Counter(r["type"] for r in rows))
    res["other_type_rows"] = sum(r["type"] == "other" for r in rows)
    res["type_unit"] = {f"{s}|{t}|{u}": n for (s, t, u), n in Counter((r["_src"], r["type"], str(r["unit"])) for r in rows).items()}
    res["answer_python_type_by_type"] = {
        f"{t}|{k}": n for (t, k), n in Counter((r["type"], type(r["answer"]).__name__) for r in rows).items()
    }
    # Numeric precision per (source, type).
    prec = defaultdict(Counter)
    ranges = defaultdict(list)
    for r in rows:
        if isinstance(r["answer"], str):
            continue
        key = f"{r['_src']}|{r['type']}"
        prec[key][decimals(r["answer"])] += 1
        ranges[key].append(float(r["answer"]))
    res["decimals"] = {k: dict(sorted(v.items())) for k, v in prec.items()}
    res["ranges"] = {
        k: {
            "min": min(v),
            "p50": statistics.median(v),
            "p99": sorted(v)[int(len(v) * 0.99) - 1],
            "max": max(v),
        }
        for k, v in ranges.items()
    }
    # Unit named in the question text vs the unit field (measures only).
    mism = []
    chk = 0
    for r in rows:
        if r["type"] not in ("area", "volume", "length"):
            continue
        chk += 1
        named = [u for u, rx in UNIT_IN_Q if rx.search(r["question"])]
        if r["unit"] not in named:
            mism.append([r["path"], r["question"][:120], r["unit"], named])
    res["unit_named_in_question"] = {"checked": chk, "not_named": len(mism), "examples": mism[:8]}

    # Text answers.
    txt = [r for r in rows if isinstance(r["answer"], str)]
    res["text_rows"] = len(txt)
    res["text_rows_by_source"] = dict(Counter(r["_src"] for r in txt))
    lens = [len(r["answer"]) for r in txt]
    res["text_answer_chars"] = {
        "min": min(lens),
        "median": statistics.median(lens),
        "p90": sorted(lens)[int(len(lens) * 0.9)],
        "max": max(lens),
    }
    res["text_multiline_share"] = round(sum("\n" in r["answer"] for r in txt) / len(txt), 4)
    res["text_with_number_share"] = round(sum(bool(re.search(r"\d", r["answer"])) for r in txt) / len(txt), 4)
    ab = [r for r in txt if ABSTAIN.search(r["answer"])]
    res["text_abstain_like"] = {
        "rows": len(ab),
        "share": round(len(ab) / len(txt), 4),
        "by_source": dict(Counter(r["_src"] for r in ab)),
        "examples": [[r["path"], r["question"][:100], r["answer"][:160]] for r in ab[:8]],
    }
    est = [r for r in txt if re.search(r"estimat|approximately|around|about|roughly", r["answer"], re.I)]
    res["text_estimate_like_rows"] = len(est)
    units_txt = Counter()
    for r in txt:
        for name, rx in (
            ("sq m", r"sq ?m\b|sqm"),
            ("m²", r"m²"),
            ("cu m", r"cu ?m\b"),
            ("m³", r"m³"),
            ("cu ft", r"cu ?ft"),
            ("feet-inch", r"\d+'-\d+"),
            ("SF", r"\bSF\b"),
            ("mm", r"\d ?mm\b"),
            ("cm", r"\d ?cm\b"),
            ("percent", r"%"),
        ):
            if re.search(rx, r["answer"]):
                units_txt[name] += 1
    res["text_unit_mentions"] = dict(units_txt)
    # A text answer that is a bare number: it could have been typed as count.
    bare = [r for r in txt if re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", r["answer"])]
    res["text_bare_number"] = [[r["path"], r["question"][:100], r["answer"]] for r in bare]
    # opening_design: count/area types answered with int and unit ft2
    res["opening_design_types"] = {
        f"{t}|{u}": n for (t, u), n in Counter((r["type"], str(r["unit"])) for r in rows if r["_src"] == "opening_design").items()
    }
    write_json(OUT_DIR / "answer_formats.json", res)
    print("text", len(txt), "abstain-like", len(ab))


if __name__ == "__main__":
    main()
