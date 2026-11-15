# Sheet symbols: toilets, urinals, sinks and windows on large raster sheets

A YOLO detector (`yolo26m`, 1024 px tiles) for four symbol classes on whole sheets of about 10,000 px, made the
same way as the door detector in `../sheet-doors/`. The labels come from the vector USACE PDFs. This directory is
research: nothing here is wired into `src/bp/`.

## Use in the app

Weights v2: `artifacts/sheet-symbols/best_v2.pt` (git-ignored, 44 MB). v1 (`best.pt`) is the older model.

The bar to wire a class in: on at least 15 held-out sheets counted by eye, the count is right on 9 of 10 sheets
where the tool answers, and the tool has a rule to abstain. Abstain rule: run the detector twice, on the sheet and
on the sheet turned 90 degrees (other tiles, other context), and answer only when both counts are equal.
`evaluate.py abstain` scores it against `handcount2.json` (15 sheets of the kinds cof, sprc and ssa, none used to
tune labels or thresholds; cof p53 is left out, as its true count is not clear).

- **Toilets: the bar is met.** Threshold 0.4 (chosen on the v1 validation set, before these counts). An exact
  count: clean render 13 right, 1 wrong, 1 abstained (13 of 14 answers right); scan look 10 right, 1 wrong,
  4 abstained (10 of 11). With a tolerance of max(1, 3 %): clean 14 / 0 / 1, scan look 11 / 0 / 4. The wrong
  answer is sprc Medium p3: 4 found, 5 by eye, and the turned pass also finds 4. Caveat: the 15 sheets hold
  about 8 different plans (the sprc sets repeat one restroom core per size), so the real rate is less sure than
  15 sheets suggest.
- **Urinals: the bar is not met. Do not use.** Exact count, clean, threshold 0.3: 8 right, 4 wrong, 3
  abstained (8 of 12). The model finds the cof urinal family (all right) and still misses most sprc wall
  urinals: at 0.4 on the clean renders it finds no urinal on 5 of the 10 sprc sheets, although cdcsa wall urinals
  were in training. The turned pass misses them too, so both passes agree on 0 and the abstain rule does not
  catch it. It also finds 1 urinal on each ssa sheet, which has none. A tolerance of max(1, 3 %) hides this (0 found for 1
  counts as right), so read the exact numbers.
- **Sinks and windows: not trained for a count in v2** (dropped from the goal). The v1 notes below still hold:
  sinks right on 2 of 10 sheets by eye, windows labelled completely only on bn-bde-hq.

A second model as the second opinion (v1 must agree with v2) gives toilets clean 13 / 1 / 1 and scan look
11 / 0 / 4 (exact), no better than the turned pass, and v1 trained on ssa. The turned pass is the rule to keep.

Size filter (long side in inches of building, from the scale of the sheet): toilet 14 to 36, urinal 10 to 24,
sink 10 to 48 (a double sink is about 42), window 18 to 120. Below or above, drop the box. Known look-alikes: a
north arrow (round with a line) was found as a sink at 0.58; fixtures of grey background plans (existing or
neighbouring buildings, drawn in halftone) are found as real fixtures.

```sh
# where ultralytics is installed (a GPU VM, or `uv run --with ultralytics` on a laptop: about 1 min a sheet on 4 cores)
python jobs/sheet-symbols/predict.py --weights artifacts/sheet-symbols/best_v2.pt sheet.png
```

One JSON per sheet in `experiments/cache/sheet-symbols/<pixel key>.json` (the key of the OCR and door caches):
`{"size": [w, h], "symbols": [{"box": [x0, y0, x1, y1], "class": "toilet", "score": 0.93}, ...]}`, every box
above score 0.05. `predict.py` runs the normal pass only: for the abstain rule, also run it on the image turned
90 degrees (`np.rot90`) and compare the counts, as `evaluate.py run` does.

## How the labels are made

- `instances.py`: the USACE PDFs are Revit prints with no layers and no XObjects, but each family instance is one
  run of consecutive drawings. A run gets a signature in inches of building (count of drawings and items, short
  and long side, line length).
- `catalog.py`: counts the loose keys of these signatures over all dev sheets and draws a contact sheet of the
  frequent ones. `similar.py` proposes names for rare keys by thumbnail likeness (8 turns).
- `classes.json`: the keys named by eye. `mask` keys are runs a person could not name for sure: they are painted
  white in the training tiles. Mop sinks and drinking fountains are left unnamed: they are background.
  `labels.py` has one extra rule: key `20x20L128` is a lavatory only with 45 items or more (with fewer it is the
  mop sink of cdcsa).
- `labels.py`: windows get a box 8 in deep (the wall), and window boxes on one line with a gap below 10 in join.
- Checked by eye on overlays of cof, sprc, cdcsa, bn-bde-hq and ortc sheets (also kinds not named from), and by
  hand counts on 5 validation sheets (`handcount.json`).

Label completeness per building kind (by eye on overlays):

| kind | toilet | urinal | sink | window |
|---|---|---|---|---|
| bn-bde-hq | complete | complete | complete | complete |
| ortc | complete | few | latrine lavatories missing | about 60 % |
| cof | complete (p53 misses some) | complete | about 90 % | none drawn |
| sprc | complete | complete after `8x14L64` | counter lavatories masked | none drawn |
| cdcsa | elongated family missing | complete after `8x14L64` | rectangular lavatory added late; counters missing | about 30 % |
| gpw, fs, ssa | partial | partial | partial | none |

## Training and validation

v2 (this commit):

- `prepare.py`: renders each dev page at 5,200 to 12,000 px long side, a clean view and views with the scan look
  of the door job (skew or a right-angle turn, line weight, grey ink, blur, noise, JPEG), and cuts 1024 px tiles.
  Validation kinds are cof, sprc (as for the doors) and ssa. cdcsa trains: it has toilet and urinal families no
  other kind has. The lock kinds of `usace.LOCK` are never read. Site plans (more than 16 ft per inch) are left
  out. 56 training pages (toilet 412, urinal 69 labels), 18 validation pages (toilet 104, urinal 39), 5,731 tiles.
- New in the labels: 5 more toilet keys (the elongated cdcsa families), and one fixture when the run of a seat
  lies inside the run of the whole fixture (`labels.py`).
- `train.py`: 26 epochs, batch 24, on one RTX PRO 6000 (37 min).
- `evaluate.py run` renders the validation sheets whole and runs the tiled detector, also on the sheet turned
  90 degrees; `score` matches detections to labels (IoU 0.3 or a centre inside); `hand` compares counts with
  `handcount.json`; `abstain` gives right, wrong and abstained against `handcount2.json`.

v2 against the labels of the 18 validation sheets, clean render: toilet at 0.4 precision 0.81, recall 0.98,
count right (max(1, 3 %)) 17 of 18; urinal at 0.3 precision 0.81, recall 0.85, count right 16 of 18.

v1 (commit 1b54c8d1; validation kinds cof, sprc and cdcsa, 41 training pages, 8,290 tiles, 28 epochs), whole
validation sheets, clean render, against the labels (33 sheets). The labels are incomplete, so precision is too
low: most "false positives" at 0.5 are real fixtures and windows without a label.
| class | thr | precision | recall | count right, all sheets | count right, sheets with the class | count right by eye (10) |
|---|---|---|---|---|---|---|
| toilet | 0.4 | 0.76 | 0.90 | 26/33 | 24/29 | 7/10 |
| urinal | 0.5 | 0.68 | 0.33 | 23/33 | 11/20 | 3/10 |
| sink | 0.7 | 0.50 | 0.52 | 15/33 | 7/23 | 2/10 |
| window | 0.5 | 0.21 | 0.26 | 26/33 | 3/9 | 4/10 (the 4 are the sheets with no windows) |

The scan-look render (variant 1) gives toilet 0.73 / 0.83 and count right 28/33 at 0.5.

## Next step

- Urinals: look at crops of the sprc wall urinal misses in both passes,
  and add more wall urinal views to training (other scales, the 1/16 in plans).
- Windows: a rule that does not depend on the width: a window is a run of 3 to 4 parallel lines inside a wall
  opening, whatever its length.
