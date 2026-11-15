# Open questions for Stoa

Date: 14 November 2026. Take these to the Stoa stand. They are ranked by how much the answer changes our plan.
`HOST.md` holds what the host already told us on Friday night. This list holds only what is still open.

For each question: why we ask, and what we do until we know.

## Scoring

| # | Question | Why it matters | Our default until we know |
|---|---|---|---|
| 1 | How do you score "I don't know"? Is a correct "this cannot be determined from this sheet" a correct answer? Is a wrong number worse than an abstention? | It sets our confidence threshold. With a penalty for wrong answers we abstain under 50% confidence. With no penalty we never abstain | We abstain only when a needed fact is missing, and we always show a best estimate beside the reason |
| 2 | When the drawing has no scale and the user gives one (two clicks, or "1:100"), does the answer after that count? | The host said "give us a scale or calibrate". It decides how much the calibration step is worth | We build the calibration step and score it as a separate column |
| 3 | Which counting rule applies when the question does not state one? In the public swiss answers a door between two apartments counts once per apartment, and the answer equals the visible doors on 7% of floors. On cubicasa, open doorways are excluded | A correct count by eye is "wrong" against such a key | We state the rule with each count and show the other value beside it. We default to what a person would count on the sheet |
| 4 | How are free-text answers graded: by a person, by a model, by key facts? | 820 public questions have long text answers and no published rule | A fact check: the required numbers and codes must be in the answer |
| 5 | Is the 2% tolerance applied to the rounded key? Some keys are rounded more coarsely than 2% (0.22 m² for 0.2249 m²) | 50 public rows fail an exact answer for this reason | We round like the key: 2 decimals |
| 6 | Does the evidence view count per answer, or once for the whole product? Who verifies: your engineers, with a timer? | It sets the effort on the evidence view against raw accuracy | Every answer carries its evidence, and we time a teammate |

## The hidden set

| # | Question | Why it matters | Our default until we know |
|---|---|---|---|
| 7 | How many documents and questions are in the hidden evaluation, and do you run it by hand through our interface for every team? | A hand-run session of a few tens of questions is noisy, and one crash weighs a lot | We plan for a short live session: no crash, under a minute per document |
| 8 | Which kinds of file can appear: historic scans, hand drawings, raster plans without a scale bar, DWG, US sheets in feet and inches, PDFs with many sheets? | About 8,600 drawings in the release have no public question. We do not know which of them matter | We weigh scans and rasters at about 40% of our own score |
| 9 | Can one question need two files, for example a plan and a schedule on another sheet, or a sheet and its model? | 170 public questions ask about a whole model while naming one sheet | One document per session. We answer "not on this document" and name what is missing |
| 10 | Which languages can the hidden questions use? The public questions use 11. The brief says about 30 | It decides how we test the question parser | The model that writes the plan reads any language. We test 6 unseen ones |
| 11 | The example "how many square metres of tiles for the toilets": floor area only, or also wall tiles? Do such questions state their assumptions? | Wall tiles need a room height, which a plan does not have | Floor area, with the assumption stated, and the height named as missing for wall tiles |
| 12 | For a 3D model: what must the interface show for you to accept an answer? Highlighted elements, a list of ids, a section view? | The host said that 3D is judged through our UI | Highlighted elements in a 3D view, with their ids |

## Cost and rules

| # | Question | Why it matters | Our default until we know |
|---|---|---|---|
| 13 | How do you measure cost: do we report it, or do you read it from a bill? Does a model on our own GPU count, and how? Is ingestion counted once per document? | The target is 10 cents for ingestion plus the questions | We log each model call at list price and GPU seconds at the cloud price, and we show the cost on each answer |
| 14 | Is there a time limit for ingestion or for an answer? | A person waits in a live session | Ingestion under 60 s, an answer under 10 s |
| 15 | May a solution use the public originals of the drawings? The cubicasa5k images are identical to the public CubiCasa5K set, and its public annotation reproduces the public answers. The same holds for Swiss Dwellings and IFC-Bench v2 | We do not use these at inference: it would be a lookup, not a solution. We want to know if training a detector on the public annotations is acceptable, and if the hidden drawings come from the same public sets | We train only on the public train split, and we never read an annotation at inference |

## A note on question 15

We recommend that Henrik tells Stoa what we found: the public answers can be reproduced from public data
without a model, and a guess of the most common answer scores 55% on two thirds of the questions. It shows
that we measure before we build, and it protects us if another team presents a high public score.

## Already answered by the host

See `HOST.md` for the quotes: the hidden set decides most of the score and is harder (rows 1, 2); one
document at a time through our interface (row 9); about 10 cents for ingestion and query (row 10); the
interface weighs about 5% unless there is a tie (row 11); most drawings have a scale and some do not (row 12);
a hint about the hidden questions comes on Saturday at about midday (row 15).
