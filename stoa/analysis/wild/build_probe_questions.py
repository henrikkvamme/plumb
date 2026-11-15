# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write the probe questions for the drawings that have no public questions: 25 on opening_design sheets that are
not the 3 sheets with questions, and 25 on historic scans (habs, finna, europeana, wikimedia).

Every answer was read on the sheet by eye (zoomed render) or parsed and then checked by eye. how_verified says
which. Five historic rows have no answer on the sheet: the answer is "cannot be determined - <reason>", with
unit null and the type of the quantity the question asks for.

Checks that each path exists under data/junction-dataset/ and that no opening_design row uses a sheet that has
public questions. Writes docs/research/data/wild-probe-questions.jsonl.
Run: uv run stoa/analysis/wild/build_probe_questions.py
"""
import collections
import json
from pathlib import Path

STOA = Path(__file__).resolve().parents[2]
DS = STOA / "data/junction-dataset"
OUT = STOA / "docs/research/data/wild-probe-questions.jsonl"

AAL = "data/opening_design/Aalseth_Residence/Transfer/20190321 - to lumber yard - latest plans with door and window schedule/Sheet A600 - 3196 Aalseth Lane - Schedules.pdf"
VR = "data/opening_design/Vacation_Rental/Transfer/20170519 ----- ISSUE FOR BID & PERMIT -------/"
A501 = VR + "The Downtowner_ARCH - Sheet - A501 - SCHEDULES.pdf"
A500 = VR + "The Downtowner_ARCH_2D and Schedules - Sheet - A500 - ADA RESTROOM & SCHEDULES.pdf"
MCK = "data/opening_design/6060_McKee-Rd/Transfer/20161014 - permit/20161014 - 6060_McKee_Rd - Permit.pdf"
JOH = "data/opening_design/725_E_Johnson/Transfer/20191105 - to GC - for review before permit/20191106 - 725 E Johnson - Drawings.pdf"
XSC = "data/opening_design/Sports_Complex/Transfer/_Archive/20150814 - Issued for Permit/"
G100 = XSC + "XSC - G-100 - Cover.pdf"
A801 = XSC + "XSC - A-801 - Door and Finish Schedules & Wall Types.pdf"

EYE = "read by eye on a zoomed render (pdf_peek.py)"
TXT = "text layer (pdf_peek.py --text), then checked by eye on a zoomed render"
CD = "cannot be determined - "

pre_aal = "On sheet A600 of the Aalseth Residence drawings (3196 Aalseth Ln, Stoughton, WI), "
pre_501 = "On sheet A501 (Schedules) of The Downtowner vacation rental drawings, issue for bid and permit 2017-05-19, "
pre_500 = "On sheet A500 (ADA Restroom & Schedules) of The Downtowner vacation rental drawings, issue for bid and permit 2017-05-19, "
pre_mck = "On sheet A101 of the 6060 McKee Rd (Fitchburg, WI) permit set, "
pre_joh = "On sheet A101 of the 725 E Johnson St (Madison, WI) drawings for Palisade Property, "
pre_xsc = "On the 2015-08-14 'Issued for Permit' set of the Xcel Sports Complex, "

OD = [
    (AAL, pre_aal + "what is the grand total number of windows in the window schedule?", 39, "count", "count",
     TXT + "; rows 7+4+3+1+3+1+19+1 = 39 and the printed grand total is 39"),
    (AAL, pre_aal + "how many windows in the window schedule are casement windows?", 30, "count", "count",
     TXT + "; window types 01, 03, 04 and 07 are casements"),
    (AAL, pre_aal + "how many exterior doors does the door schedule list in total?", 10, "count", "count", TXT),
    (AAL, pre_aal + "what is the grand total area in the room schedule?", 3672, "ft2", "area",
     TXT + "; the printed grand total is 3672 SF but the printed rows sum to 3671 SF (Revit rounds each row). "
     "Level totals: basement 1091, garage level 1398, 2nd floor 1182"),
    (A501, pre_501 + "how many walls does the wall schedule list in total?", 85, "count", "count",
     TXT + "; printed grand total 85 walls, 8330 SF"),
    (A501, pre_501 + "what is the total area of slotted wood fence in the wall schedule?", 1159, "ft2", "area",
     TXT + "; printed subtotal 1159 SF, the printed rows sum to 1160 SF"),
    (A501, pre_501 + "how many tempered insulated glazing units (Cardinal LoE-240) does the glazing schedule list?",
     26, "count", "count", TXT + "; the same rows total 584 SF"),
    (A500, pre_500 + "how many entries does the door schedule list?", 46, "count", "count",
     EYE + "; SWING 13 + SLIDER 16 + STOREFRONT 15 + GATE DOOR 2 = 46 rows. Door numbers 103.A, 104.B and 105.A "
     "appear twice, so a count of distinct door numbers gives 43 - an ambiguous question on purpose"),
    (A500, pre_500 + "how many doors in the door schedule are slider doors?", 16, "count", "count", EYE),
    (A500, pre_500 + "how many doors in the door schedule have the note '180 DEGREE OPEN'?", 7, "count", "count", EYE),
    (A500, pre_500 + "what are the width and height of window type W1?", "3'-1\" wide x 3'-1\" high", None, "text",
     EYE + "; 7 windows of type W1"),
    (MCK, pre_mck + "what is the total area of the rooms in the finish (room) schedule?", 485, "ft2", "area",
     TXT + "; Corridor 117 + Women's Locker 201 + Util. Closet 23 + Men's Locker 144"),
    (MCK, pre_mck + "what is the total area of the rooms that have a porcelain tile floor?", 345, "ft2", "area",
     TXT + "; Women's Locker 201 + Men's Locker 144, checked row by row against the floor finish column"),
    (MCK, pre_mck + "what approximate area does the overall floor plan note give for the tenant suite?", 3080,
     "ft2", "area", EYE + "; printed '~3080 SF'; the renovation area is printed as '~550 SF'"),
    (MCK, pre_mck + "what is the scale of the 1st floor plan?", "1/2\" = 1'-0\"", None, "text", EYE),
    (JOH, pre_joh + "what is the grand total occupant load in the room schedule?", 10.5, "count", "count",
     TXT + "; printed grand total 10.5, the printed rows sum to 10.6 (rounding). Total area of the 11 rooms 1347 SF"),
    (JOH, pre_joh + "what is the total area of the 3 offices in the room schedule?", 385, "ft2", "area",
     TXT + "; 139 + 123 + 123"),
    (JOH, pre_joh + "how many of the doors in the door schedule are marked '1st Phase'?", 6, "count", "count",
     TXT + "; 6 of 8 doors"),
    (JOH, pre_joh + "what is the length of the SF-1 pre-fabricated glass wall?", 59, "ft", "length",
     EYE + "; printed 59'-0\" (17.98 m). The dataset uses unit m for length; this sheet is in feet"),
    (JOH, pre_joh + "how many chairs are drawn at the table in meeting room 102?", 6, "count", "count",
     EYE + "; counted symbols on a zoom. Floor plan scale 1/4\" = 1'-0\""),
    (G100, pre_xsc + "how many sheets does the sheet list on cover sheet G-100 list?", 37, "count", "count",
     EYE + "; 31 A-sheets, 4 C, 1 G, 1 S. Text-line extraction alone found 35 (it merged 2 rows)"),
    (G100, pre_xsc + "what total occupant load does cover sheet G-100 give?", 677, "count", "count",
     EYE + "; the 24hr Fitness Center alone is 82"),
    (A801, pre_xsc + "how many doors does the door schedule on sheet A-801 list?", 41, "count", "count",
     "od_probe_schedule.py, then every row checked by eye. The CURRENT A-801 (the sheet with public questions) "
     "lists 38: this archive revision adds 114.A, 120.A/B, 121.C, 123.A, 126.A and lacks 122.B/C, 124.B"),
    (A801, pre_xsc + "what area does the finish schedule on sheet A-801 give for Fitness Center 118?", 4068, "ft2",
     "area", "od_probe_schedule.py, checked by eye; the current A-801 gives 5183 SF"),
    (A801, pre_xsc + "what are the width and height of door 128.B on sheet A-801?", "9'-0\" wide x 12'-0\" high",
     None, "text", "od_probe_schedule.py, checked by eye; the current A-801 gives 12'-0\" x 14'-0\". "
     "Golf Simulator 114 (1123 SF) exists only in this revision"),
]

H = "data/habs/"
FI = "data/finna/"
EU = "data/europeana/"
WI = "data/wikimedia/"
HIST = [
    (H + "or0036_sheet_00003.jpg", "On this HABS sheet (Samuel Brown House, Gervais, Oregon, second floor plan), "
     "how many bedrooms are labeled?", 3, "count", "count",
     "read by eye on a zoom (img_peek.py): Bed Room #3, #4, #5. Scale 1/4\" = 1'-0\", sheet 3 of 14"),
    (H + "ny0248_sheet_00000.jpg", "According to this HABS cover sheet, in which year was Fifty-Seven Willow Street, "
     "Brooklyn, erected?", "1824", None, "text",
     "read by eye: 'Architect - unknown, Builder - unknown, Erected in 1824'. The LICENSE.md title names the "
     "building 'Harold J. Szold House', a name the sheet does not use"),
    (H + "ny0248_sheet_00000.jpg", "How many rooms are on the second floor of the house shown on this sheet?",
     CD + "this is the cover sheet (title, location sketch map and survey data); it has no floor plan",
     None, "count", "read by eye: the sheet holds a title, a sketch map and a text block only"),
    (H + "ut0098_sheet_00002.jpg", "On the upper floor plan of the Town Hall in Ophir, Utah, how many rooms are "
     "labeled?", 3, "count", "count",
     "read by eye on a zoom: Meeting Hall, Fire Department, Storage Room. The lower floor plan has Jail"),
    (H + "ut0098_sheet_00002.jpg", "What is the overall exterior width of the upper floor plan of the Town Hall "
     "in Ophir, Utah, as dimensioned?", 26.42, "ft", "length",
     "read by eye on a zoom: printed 26'-5\" (8.05 m). The lower floor plan prints 26'-6\" for the same wall"),
    (H + "pa1137_sheet_00002.jpg", "On the elevation looking north of the Dingmans Ferry Bridge, how many truss "
     "spans does the bridge have?", 3, "count", "count",
     "read by eye: 3 trusses on 2 piers. Elevation scale 1\" = 30'-0\""),
    (H + "sc0350_sheet_00004.jpg", "What is the floor area of Crowfield Hall according to this sheet?",
     CD + "the sheet shows only the north elevation (scale 1/4\" = 1'-0\"); there is no plan and no floor "
     "dimension", None, "area", "read by eye: one elevation, 8 window openings and 1 door"),
    (FI + "hka.139879309684900_167350795672900.jpg", "In section A-B of this 1889 drawing for a lot on Berggatan "
     "(Vuorikatu 16), Helsinki, how many storeys are shown above the basement?", 5, "count", "count",
     "read by eye on a zoom: 5 storeys above a low basement"),
    (FI + "hka.139879309684900_167350795672900.jpg", "In which year was this drawing for a lot on Berggatan, "
     "Helsinki, signed?", "1889", None, "text",
     "read by eye: 'Helsingfors i November 1889'. The LICENSE.md title also gives (1889): a metadata shortcut"),
    (FI + "hka.139879309684900_166229673923400.jpg", "On the facade toward Fredriksgatan in this 1886 drawing, "
     "how many windows are on the three main storeys above the basement?", 21, "count", "count",
     "read by eye on a zoom: 7 per storey x 3. Not counted: the door and 4 basement windows"),
    (FI + "hka.139878174949000_146761793020700.jpg", "What scale is this site plan of the elementary school at "
     "Lapinlahdenkatu 6 drawn at?", "1:500", None, "text",
     "read by eye on a zoom: '1/500' in the title block. At contact-sheet size it reads like 1/800"),
    (FI + "hka.139878174949000_146761793020700.jpg", "What date is written in the title block of this site plan "
     "of the elementary school at Lapinlahdenkatu 6?", "5 December 1959 (5/12/59)", None, "text",
     "read by eye on a zoom; drawing no. 8, title block in Finnish and Swedish"),
    (FI + "hka.139878174949000_146770177139800.jpg", "At what scale is this drawing drawn?",
     CD + "the file is a handwritten document in Swedish, not a drawing; it has no scale", None, "text",
     "read by eye: handwritten text with signatures and a stamp '23 II 3'"),
    (EU + "126_https___www_searchculture_gr_aggregator_edm_travelogues_000116_46712.jpg",
     "How many minarets does the elevation of the Mosque of Sultan Ahmed on this plate show?", 6, "count",
     "count", "read by eye on a zoom: title 'L'elevation et le plan de la Mosquee de Sultan Achmed'"),
    (EU + "9200579_nq89qwen.jpg", "Who is named as the architect of the Mansel Lacey National Schools on this page?",
     "Mr. Nicholson", None, "text",
     "read by eye: header 'MANSEL LACEY NATIONAL SCHOOLS, HEREFORDSHIRE.-MR. NICHOLSON, ARCHITECT', The Builder "
     "Vol. XI No. 542 p. 405. The LICENSE.md title says 'Hertfordshire' and the credit names the engraver Laing"),
    (EU + "401_item_KOZNLHVBB62BZBKALGRHGXM6BTY2V4FH.jpg", "What is the floor area of the Saal (hall) on this "
     "Kihnu manor ground plan?", CD + "the sheet has no scale bar, no scale ratio and no dimensions", None,
     "area", "read by eye: hand-drawn plan, Estonian room labels and a north arrow only"),
    (EU + "378_https___repozitorij_muo_hr__pr_i_id_10247.jpg", "How many rooms are labeled on the floor plan of "
     "this house?", 4, "count", "count",
     "read by eye on a zoom: Staja, Soba, Kuhinja, Komora. One unlabeled room and the porch are not counted"),
    (EU + "126_https___www_searchculture_gr_aggregator_edm_travelogues_000116_44498.jpg",
     "How many columns does the elevation of the tomb at Mylasa show?", 4, "count", "count",
     "read by eye: 'Elevation du tombeau de Mylasa', scale bar in pieds, Pl. 86"),
    (EU + "15508_https___id_kulturpool_at_00e07364_60b3_442b_bb26_6823d6c3dd55_cho.jpg",
     "What is the overall length of the 2nd floor plan of the Tesstal sanatorium, as dimensioned?", 39.8, "m",
     "length", "read by eye: bottom chain 10.90 + 18.00 + 10.90 = 39.80. The source is only 1200 px wide, so "
     "the middle figure is hard to read; the sum confirms it. Architect Professor Alfred Castelliz"),
    (WI + "59450583.jpg", "Using the scale bar, what is the overall length of the Memmingen synagogue ground floor "
     "along its long axis?", 24.7, "m", "length",
     "measure_scale.py: bar 137 px = 5 m, outer extent 678 px, so 24.7 m (about +-0.3 m)"),
    (WI + "47148875.jpg", "How many shops (Butik) are labeled on this 1905 basement plan for lot 19 in the "
     "Baggen block?", 4, "count", "count", "read by eye on a full render: 4 'BUTIK' labels and 1 'TVATTSTUGA'"),
    (WI + "47148875.jpg", "Using the scale bar, what is the overall width (left to right) of the building on this "
     "1905 basement plan?", 25.6, "m", "length",
     "measure_scale.py plus a tick scan: 0 and 15 m ticks at x 762 and 1790, 68.5 px/m; outer extent 1753 px, "
     "so 25.6 m (about +-0.3 m)"),
    (WI + "93979376.jpg", "On this general plan, which building does number 1 mark?",
     "Oleksandrivskyi kostel (Олександрівський костьол, the Alexander church)", None, "text",
     "read by eye: key item 1. The key has 8 items; scale bar 0-50"),
    (WI + "15846230.jpg", "Who drew the plan shown on this board, and in which year?", "G. Seebach, 1982", None,
     "text", "read by eye: caption 'gez. von G. Seebach, Original 1:100, 1982'. The file is a camera photo of a "
     "board, so 1:100 does not apply to the image. The LICENSE.md title gives only 'Ruine schauenstein juni2010 3'"),
    (WI + "10058174.jpg", "What is the overall length of the building in metres?",
     CD + "the sheet has no scale bar, no scale ratio and no dimension; it shows only spot levels +6.70, +7.00 "
     "and +8.96", None, "length",
     "read by eye. The LICENSE.md title names the Zagreb Synagogue, but the sheet gives no length"),
]

qpaths = {json.loads(l)["path"] for l in open(DS / "questions.jsonl")}
rows = []
for group, items in (("opening_design", OD), ("historic", HIST)):
    for path, q, a, unit, typ, how in items:
        assert (DS / path).is_file(), f"missing: {path}"
        if group == "opening_design":
            assert path not in qpaths, f"sheet has public questions: {path}"
        rows.append({"path": path, "question": q, "answer": a, "unit": unit, "type": typ, "how_verified": how})
assert len(OD) == 25 and len(HIST) == 25
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
src = collections.Counter(r["path"].split("/")[1] for r in rows)
typ = collections.Counter((r["path"].split("/")[1] == "opening_design", r["type"],
                           isinstance(r["answer"], str) and r["answer"].startswith("cannot")) for r in rows)
print(len(rows), dict(src))
print({f"{'od' if k[0] else 'hist'}/{k[1]}{'/no-answer' if k[2] else ''}": v for k, v in sorted(typ.items())})
