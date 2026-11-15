"""The `sheets` suite: questions on large professional sheets, of the kind Stoa showed on 14 November.

    uv run python jobs/sheets/build_suite.py [--render]

Stoa's examples of the hidden set are PNG renders of pages of public drawing sets: UK Department for Education
model school plans, US Army standard design AW 078-24-33 and the US Air Force dormitory standard design. The
sources are vector PDFs, so the text on each sheet is exact. This script reads that text for the keys and renders
each page to a PNG the way Stoa did (600 dpi, or 300 dpi when the long side would pass 14,000 px). A solver sees
only the PNG.

Put the PDFs in `data/external/sheets/` (not in git; `SOURCES` has the addresses). Families:

- `label_count`: how many rooms carry a label. The key is the number of text labels with that exact text.
- `printed_area`, `printed_area_m2`, `printed_area_sum`: an area printed next to a room name, in square feet.
- `tag_count`: how many different equipment tags with one prefix are on the sheet (PS-1, PS-2, ...).
- `scale`: the scale printed for the one drawing on the sheet.
- `zone_area`: the area of one colour zone of a dormitory plan. The key is the area that the legend prints. Only
  the T-shape and the U-shape sheets, checked by eye: the L-shape sheets draw one wing with a break line, so the
  drawing is shorter than the building, and the upper floors colour the voids ("open to below") as common area.

Not covered yet, because the key needs geometry and a check by hand: areas from room shapes, baseboard length,
door and window counts, slab area by type.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

import usace
from bp.contract import CountKey, Item, LookupKey, MeasureKey
from bp.suites import write_items

STOA = Path(__file__).resolve().parents[2]
SRC = STOA / "data" / "external" / "sheets"
OUT = STOA / "data" / "sheets-test"
SOURCES = {
    "uk_dfe": "https://www.gov.uk/government/publications/a-new-model-design-for-a-special-school (and -primary-, -secondary-)",
    "us_aw_078-24-33": "https://nibs-s3-wbdg3-production.s3.us-east-1.amazonaws.com/FFC/DOD/COS/AW_078-24-33.pdf",
    "us_daf_dorm": "https://www.wbdg.org/FFC/AF/AFDP/PERM_PARTY_ENLISTED_DORM/Dorm_SD_Drawings.pdf",
}
SQFT_M2 = 0.09290304
Question = tuple[str, str, object, str]


def labels(page: pymupdf.Page) -> list[str]:
    """The text labels of a page: lines stacked on each other with the same centre join to one label."""
    lines: list[tuple[float, float, float, float, str]] = []  # centre x, top, bottom, height, text
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join("".join(s["text"] for s in line["spans"]).split())
            if not text or abs(line["dir"][0]) < 0.99:
                continue
            x0, y0, x1, y1 = line["bbox"]
            lines.append(((x0 + x1) / 2, y0, y1, y1 - y0, text))
    lines.sort(key=lambda v: (round(v[1], 1), v[0]))
    used = [False] * len(lines)
    out: list[str] = []
    for i, first in enumerate(lines):
        if used[i]:
            continue
        used[i] = True
        parts, cx, bottom, height = [first[4]], first[0], first[2], first[3]
        grew = True
        while grew:
            grew = False
            for j, other in enumerate(lines):
                if used[j] or abs(other[3] - height) > 0.15 * height:
                    continue
                if abs(other[0] - cx) < 0.6 * height and -0.3 * height < other[1] - bottom < 0.5 * height:
                    used[j], grew = True, True
                    parts.append(other[4])
                    bottom = other[2]
                    break
        out.append(" ".join(parts))
    return out


def label_questions(page: pymupdf.Page) -> list[Question]:
    counts = Counter(labels(page))
    names = [n for n in counts if re.fullmatch(r"[A-Z][A-Za-z'&/() -]{3,40}", n) and not n.isupper()]
    out: list[Question] = []
    for name in sorted(names, key=lambda n: (-counts[n], n)):
        # a label that is part of another label ("Store" in "Secure Store") has no clear count
        if counts[name] < 2 or any(name != o and name.lower() in o.lower() for o in counts):
            continue
        out.append(("label_count", f"How many rooms on this plan are labelled '{name}'?",
                    CountKey(value=counts[name]), "count/raster"))  # fmt: skip
    return out[:5]


def printed_areas(page: pymupdf.Page) -> dict[str, list[int]]:
    """Room name -> the areas printed with it ("645 SF" above the name)."""
    rows = [" ".join(line.split()) for line in page.get_text("text").splitlines() if line.strip()]
    found: dict[str, list[int]] = defaultdict(list)
    i = 0
    while i < len(rows):
        m = re.fullmatch(r"([\d,]+) SF", rows[i])
        i += 1
        if not m:
            continue
        name: list[str] = []
        while (
            i < len(rows)
            and re.fullmatch(r"[*A-Z][A-Z /()\-*]*", rows[i])
            and len(name) < 4
            and not rows[i].startswith(("ENTIRE", "GROSS", "MODULE", "SCALE"))
        ):
            name.append(rows[i].strip("* "))
            i += 1
        text = " ".join(name).replace(" / ", "/").replace("/ ", "/").strip()
        if text and "OPEN TO" not in text and "SCALE" not in text:
            found[text].append(int(m.group(1).replace(",", "")))
    return found


def area_questions(page: pymupdf.Page) -> list[Question]:
    out: list[Question] = []
    for name, values in sorted(printed_areas(page).items()):
        room = name.lower()
        if len(values) == 1:
            out.append(("printed_area", f"What floor area does this plan print for the room '{room}', in square feet?",
                        MeasureKey(value=float(values[0]), unit="sqft", tolerance=0.005, decimals=0), "lookup/raster"))  # fmt: skip
            out.append(("printed_area_m2", f"What is the floor area of the room '{room}' on this plan, in m2? "
                        "The plan prints areas in square feet.",
                        MeasureKey(value=round(values[0] * SQFT_M2, 2), unit="m2", tolerance=0.01, decimals=1),
                        "compound/raster"))  # fmt: skip
        elif len(values) <= 4:
            out.append(("printed_area_sum", f"What is the total floor area of all rooms labelled '{room}' on this plan, "
                        "in square feet?",
                        MeasureKey(value=float(sum(values)), unit="sqft", tolerance=0.005, decimals=0),
                        "compound/raster"))  # fmt: skip
    return out


def tag_questions(page: pymupdf.Page) -> list[Question]:
    tags: dict[str, set[str]] = defaultdict(set)
    for word in page.get_text("words"):
        m = re.fullmatch(r"([A-Z]{2,5})-(\d{1,3}[A-Z]?)", word[4].strip(",.;()"))
        if m:
            tags[m.group(1)].add(m.group(2))
    out: list[Question] = []
    for prefix, numbers in sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(numbers) < 3:
            continue
        example = f"{prefix}-{min(numbers, key=lambda n: (len(n), n))}"
        out.append(("tag_count", f"How many different tags that start with '{prefix}-' are on this sheet (such as "
                    f"{example})? Count each tag once, also when it is printed more than once.",
                    CountKey(value=len(numbers)), "count/raster"))  # fmt: skip
    return out[:3]


def scale_questions(page: pymupdf.Page) -> list[Question]:
    text = " ".join(page.get_text("text").split())
    found = set(re.findall(r"SCALE: ?(1 ?: ?\d+)\b", text)) | set(re.findall(r"(?<![\d:])(1:\d{2,4})(?!\d)", text))
    ratios = {re.sub(r"\s", "", f) for f in found}
    if len(ratios) != 1:
        return []
    ratio = ratios.pop()
    number = ratio.split(":")[1]
    return [("scale", "What scale does this sheet print for its drawing? Answer as a ratio such as 1:100.",
             LookupKey(accepted=(ratio, f"1 : {number}", f"1/{number}", f"1 to {number}")), "lookup/raster")]  # fmt: skip


ZONE_SHEETS = {2, 3, 4, 8, 9, 10}  # page numbers of the dormitory set with the whole building drawn to scale
ZONE_TOLERANCE = 0.03


def zone_questions(name: str, page: pymupdf.Page) -> list[Question]:
    if not name.startswith("us_daf_dorm") or int(name[-3:]) not in ZONE_SHEETS:
        return []
    text = " ".join(page.get_text("text").split())
    printed = {k.strip(): int(v.replace(",", "")) for k, v in re.findall(r"([A-Z][A-Z ]+?) ([\d,]+) SQ\.FT\.", text)}
    dormitory = next((v for k, v in printed.items() if k.endswith(("DORMITORY", "DORMITORY AREA"))), None)
    circulation = [v for k, v in printed.items() if k.endswith("CIRCULATION") and "MODULE" in k]
    common = next((v for k, v in printed.items() if k.endswith("COMMON AREA")), None)

    def ask(zone: str, value: int) -> Question:
        return ("zone_area", f"What is the total floor area of the {zone} zone on this plan, in square feet?",
                MeasureKey(value=float(value), unit="sqft", tolerance=ZONE_TOLERANCE, decimals=0), "compound/raster")  # fmt: skip

    out: list[Question] = []
    if dormitory:
        out.append(ask("dormitory", dormitory))
    if len(circulation) == 2:
        out.append(ask("circulation", sum(circulation)))
    if common and "FIRST FLOOR PLAN" in text:
        out.append(ask("common area", common))
    return out


def render(page: pymupdf.Page, path: Path) -> None:
    long_side_in = max(page.rect.width, page.rect.height) / 72
    dpi = 600 if long_side_in * 600 <= 14100 else 300
    page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False).save(path)


def sheets() -> list[tuple[str, str, pymupdf.Page]]:
    """(name, group, page) for each sheet that the suite uses."""
    out: list[tuple[str, str, pymupdf.Page]] = [
        (f"uk_dfe_{pdf.stem.lower()}_p001", f"uk_dfe:{pdf.stem[:3]}", pymupdf.open(pdf)[0])
        for pdf in sorted((SRC / "uk_dfe").glob("*-D-X-*.pdf"))
    ]
    for stem, group in (("us_daf_dorm_sd_drawings", "us_daf_dorm"), ("us_aw_078-24-33", "us_aw_078-24-33")):
        doc = pymupdf.open(SRC / f"{stem}.pdf")
        for i, page in enumerate(doc):
            title = " ".join(page.get_text("text").split())
            if "PLAN" in title:
                out.append((f"{stem}_p{i + 1:03d}", group, page))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true", help="write the PNG of each sheet that has a question")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    items: list[Item] = []
    for name, group, page in sheets():
        asked = label_questions(page) + area_questions(page) + tag_questions(page) + scale_questions(page)
        asked += zone_questions(name, page)
        if not asked:
            continue
        if args.render and not (OUT / f"{name}.png").exists():
            render(page, OUT / f"{name}.png")
        for family, text, key, cell in asked:
            ident = hashlib.sha256(f"{name}:{family}:{text}".encode()).hexdigest()[:14]
            items.append(Item(
                item_id=f"sh-{ident}", doc=f"../sheets-test/{name}.png", question=text, key=key,  # ty: ignore[invalid-argument-type]
                source=group.split(":")[0], family=family, group=group, cell=cell,
                suite="sheets", condition="sheet", partition="val", origin="derived",
            ))  # fmt: skip
    for name, group, partition, page in usace.sheets(SRC / "usace"):
        printed, hidden, area_lines = usace.questions(name, page)
        long_side_in = max(page.rect.width, page.rect.height) / 72
        dpi = 600 if long_side_in * 600 <= 14100 else 300
        for asked, stem in ((printed, name), (hidden, f"{name}_noarea")):
            if not asked:
                continue
            if args.render and not (OUT / f"{stem}.png").exists():
                if stem == name:
                    render(page, OUT / f"{stem}.png")
                else:
                    usace.render_without_areas(page, area_lines, OUT / f"{stem}.png", dpi)
            for family, text, key, cell in asked:
                ident = hashlib.sha256(f"{stem}:{family}:{text}".encode()).hexdigest()[:14]
                items.append(Item(
                    item_id=f"sh-{ident}", doc=f"../sheets-test/{stem}.png", question=text, key=key,  # ty: ignore[invalid-argument-type]
                    source="usace", family=family, group=group, cell=cell,
                    suite="sheets", condition="sheet", partition=partition, origin="derived",  # ty: ignore[invalid-argument-type]
                ))  # fmt: skip
    path = write_items("sheets", items)
    print(path, len(items), "items", len({i.doc for i in items}), "sheets")
    print(dict(Counter(i.family for i in items)))
    print(dict(Counter(i.source for i in items)))
    print(dict(Counter((i.partition, i.family) for i in items)))


if __name__ == "__main__":
    main()
