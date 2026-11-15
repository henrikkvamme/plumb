# Verification UX: how a person checks an AI answer about a drawing in seconds

Track: research on verification of AI output and overreliance, visual grounding and provenance interfaces,
confidence display, the construction takeoff and drawing-QA market, and Stoa itself. Written 2026-11-13.

Labels used in this file:

- **[MEASURED]**: a number we computed or observed ourselves (for example an HTTP redirect).
- **[READ]**: a number or sentence we read in the source. The source id is given.
- **[ESTIMATE]**: our own judgement or guess. Not a measurement.
- **[UNVERIFIED]**: we could not open the primary source.

Method note. The harness web search and web fetch tools were not available in this session (usage limit).
DuckDuckGo, Google, Bing and Mojeek blocked automated queries, also from a real browser. We found papers through
the OpenAlex API and read the papers on arxiv.org (abstract pages and full HTML). We read vendor and Stoa pages
by direct HTTP fetch. Every cited claim below comes from a page we opened. The market scan is narrower than a
search-engine scan would give: we could only open vendors whose domain we knew.

## Findings that change decisions

1. **Lead with checkable evidence on the drawing. Put prose rationale last or hide it.** Explanations increase
   reliance on correct AND incorrect answers. Sources reduce reliance on incorrect answers: agreement with a
   wrong LLM answer fell from 78.2% to 68.2% when sources were shown [READ, S1, N=308]. Explanations raised
   acceptance "regardless of its correctness" [READ, S6]. When an LLM explanation was wrong, users scored 0.35
   accuracy, below the no-evidence baseline of 0.49 [READ, S3]. Moves: verifiability, accuracy of the
   human-plus-AI result. Hidden set: harder questions mean more wrong answers, so fluent prose is a liability.
2. **Colour each item by confidence. A two-level colour flag more than doubled accuracy on the hard task.**
   With green/red highlighting of each number by model confidence, decision accuracy on the hard task was 58%
   (high plus low flags) and 53% (low flags only), against 26% without highlighting [READ, S12]. The cost was a
   small time increase [READ, S12]. Moves: verifiability. Hidden set: this effect appeared exactly on the task
   where the AI was least reliable, which is the hidden-set regime.
3. **Reduce the cost of checking, not the amount of explanation.** Overreliance was lower with highlight
   explanations (a path drawn on the maze, easy to check) than with written explanations [READ, S4, N=731].
   Explanations help only "to the extent that they allow a human decision maker to verify" [READ, S9]. Symbolic
   references from each generated value to its source field cut verification time by 20% [READ, S13]. Design
   consequence: a count is a set of numbered marks, an area is a polygon plus an arithmetic tape, a model answer
   is a row list of entity IDs.
4. **Marks and citations must be machine-checked before display, because their presence alone builds trust.**
   Visual explanations "engender human trust, even for incorrect predictions" [READ, S19]. Attribution maps hurt
   human-AI team accuracy on a hard fine-grained task [READ, S20]. Random citations raised self-reported trust
   [READ, S14]. Commercial generative search engines supported only 51.5% of sentences fully, and 74.5% of their
   citations supported the sentence [READ, S8]. Show rejected candidates and disagreements: visible
   inconsistencies reduced overreliance [READ, S1], and contrastive (both-sides) explanations mitigated it
   [READ, S3].
5. **People cannot read a model's confidence from its prose. Show a calibrated number in frequency format.**
   Model confidence discriminated right from wrong answers with AUC 0.75 to 0.78. Humans who read the default
   explanations reached AUC 0.59 to 0.60 [READ, S7]. Longer explanations raised user confidence without raising
   accuracy [READ, S7]. Calibrated uncertainty in a frequency format let users adjust reliance [READ, S18].
   Confidence display calibrates trust but does not raise accuracy by itself [READ, S10]. Our plan: show "right
   47 of 50 times on held-out questions of this kind" from our own evaluation [ESTIMATE of format].
6. **"I do not know" works when it is first-person and comes with a next step.** "I'm not sure, but..." lowered
   agreement from 80.9% to 74.8% and raised accuracy on wrong AI answers from 43.6% to 52.0% [READ, S2]. The Stoa
   host asked for exactly this, and for a scale request instead of a refusal: "If you want an answer, give us a
   scale or calibrate" [READ, S30, via HOST.md]. Abstention raised advice acceptance among users with high
   perceived expertise and tended to lower it among novices [READ, S23]. Construction professionals are the
   high-expertise case [ESTIMATE].
7. **The market shows evidence in two ways, and none of the pages we read shows a per-answer confidence or an
   abstention.** Takeoff tools (Togal, Kreo, Countfire, STACK, DESTINI Takeoff, Bluebeam Max) put marks or
   overlays on the drawing and keep quantities editable [READ, S32-S34, S41-S43, S48]. Q&A tools (Procore, Pelles,
   Trunk Tools, Stoa) cite the document and page [READ, S26, S36-S38]. "Done-for-you" services claim 99%+ with
   human QA in 24-72 hours [READ, S45, S46]. A per-item confidence colour, a calibrated frequency, a scale
   request and an arithmetic tape are open ground for us [ESTIMATE, limited to the pages we could open].
8. **Stoa's own product sets the judges' frame: sentence-level citations to the page, a "Show thought process"
   toggle, numbered change boxes on drawings, and "When the documents do not hold the answer, Stoa says so."**
   [READ, S26]. Their stand demo shows an issue panel with numbered citation chips beside stacked 3D floor
   plans and a Gantt chart [MEASURED from photo, S31]. Expect judges to click a number and look for its place on
   the sheet [ESTIMATE]. A team member proposed that the interface weighs about 5% and the host agreed
   ("Should be a good ballpark"). Explainability is a separate criterion [READ, S30].
9. **The human baseline is far from perfect, so the view must make correction cheap.** On 10 real residential
   blueprint sets, independent professional estimators scored 77.6% against a reconciled gold standard. Seven
   frontier and open models scored composites of 35 to 61 [READ, S25]. Vendors claim manual takeoff error rates of
   5-15% [READ, S43, vendor claim, no study cited by name]. One click per wrong mark (toggle in or out, the count
   updates) is the correction unit [ESTIMATE].
10. **Do not rely on the human check for accuracy.** A meta-analysis of 106 studies found human-AI combinations
    worse than the best of human or AI alone on average (Hedges' g = -0.23), with losses on decision tasks
    [READ, S17]. Accuracy must come from the machine verifier. The evidence view is for fast spot checks and
    for trust, not the error-correction mechanism [ESTIMATE].

## Landscape

### A. Research on reliance and verification (2020-2026)

| Id | Study | Setting | What reduced overreliance | What increased it | Effect size [READ] |
|---|---|---|---|---|---|
| S1 | Kim et al., CHI 2025 | LLM answers to objective questions, N=308 | Sources; inconsistencies inside explanations | Explanations (consistent ones most) | Wrong answer: agreement 68.2% with sources vs 78.2% without. Correct answer: 73.4% vs 67.2% |
| S2 | Kim et al., FAccT 2024 | Medical questions, fictional LLM search, N=404, pre-registered | First-person uncertainty ("I'm not sure, but...") | - | Agree 80.9% to 74.8%. Accuracy on wrong AI answers 43.6% to 52.0% |
| S3 | Si et al., NAACL 2024 | Claim fact-checking, 80 crowdworkers | Retrieved passages; contrastive explanations | LLM explanation alone | Explanation wrong: accuracy 0.35 vs 0.49 baseline vs 0.54 retrieval. Time 1.0 min (explanation) vs 2.5 min (retrieval) vs 2.7 min (both) |
| S4 | Vasconcelos et al., CSCW 2023 | Maze with simulated AI, 5 studies, N=731 | Explanations that lower verification cost (highlighted path); higher reward | Hard tasks; hard-to-parse written explanations | Highlight < written overreliance in medium and hard tasks (95% credible interval excludes 0) |
| S5 | Buçinca et al., CSCW 2021 | Nutrition task, N=199 | Cognitive forcing (on demand, wait, update) | Simple XAI | Significant reduction, but the most effective designs got the lowest subjective ratings |
| S6 | Bansal et al., CHI 2021 | 3 datasets, AI accuracy similar to human | - | Explanations | Explanations raised acceptance "regardless of its correctness" |
| S7 | Steyvers et al., Nat. Mach. Intell. 2025 | Trivia MC and short answer | Explanations that state model uncertainty | Default and longer explanations | Human AUC 0.59-0.60 vs model AUC 0.75-0.78 |
| S10 | Zhang, Liao, Bellamy, FAT* 2020 | Income prediction | Confidence score calibrated trust | Local explanations did not | Trust rose for confidence > 80%; no accuracy gain |
| S12 | Spatharioti et al., CHI 2025 (arXiv 2023, different title) | LLM search for product decisions | Green/red confidence highlighting per number | Plain LLM output | Hard task accuracy 26% (none) vs 58% (high+low) vs 53% (low only) |
| S13 | Hennigen et al. (SymGen), 2023/2024 | Data-to-text, QA | Symbolic references to source fields | - | Verification time -20%; 5% more confident |
| S14 | Ding et al., AAAI 2025 | Live chatbot QA | Checking citations lowered trust | Any citation, even random | Significant (no number in abstract) |
| S15 | Martin et al. (PaperTrail), CHI 2026 | 26 researchers | Claim-evidence map lowered trust | - | Trust fell, behaviour did not change |
| S16 | Wang et al. (Graphionale), UIST 2026 | N=204 | Graph rationales for verbal tasks | Graph rationales for visual tasks impaired calibration | Direction only in abstract |
| S17 | Vaccaro, Almaatouq, Malone, Nat. Hum. Behav. 2024 | Meta-analysis, 106 studies, 370 effects | - | - | Human-AI vs best alone: g = -0.23 (95% CI -0.39 to -0.07) |
| S18 | Cao, Liu, Huang, CSCW 2024 | Skin cancer screening | Calibrated uncertainty in frequency format | Calibrated uncertainty alone "inadequate" | Direction only in abstract |
| S19 | Kim et al. (HIVE), ECCV 2022 | ~1000 participants, 4 CV explanation methods | - | Visual explanations, also for wrong predictions | Users could not tell right from wrong |
| S20 | Nguyen et al., NeurIPS 2021 | ImageNet, dog breeds | Nearest examples as good as attribution | Attribution maps on hard task | Team accuracy below AI alone on the hard task |
| S23 | Wolczynski et al., arXiv Oct 2026 | Financial advice, pre-registered | Abstention for high-expertise users | Abstention for low-expertise users | Direction only in abstract |
| S24 | Reyes et al., arXiv Feb 2026 | Alzheimer prognosis, N=37 + 10 experts | Continuous encodings helped users see limits | Binary encodings raised momentary confidence | Direction only in abstract |

Synthesis [ESTIMATE, from the table]: the mechanisms that worked all lower the cost of finding the error
(sources, highlights, per-item flags, visible conflicts). The mechanisms that failed or backfired all add
persuasive material that is costly to check (prose, saliency maps, citations nobody opens, argument graphs on
visual tasks).

### B. Visual grounding and provenance patterns

| Pattern | Evidence | Fit for drawings [ESTIMATE] |
|---|---|---|
| Numbered marks on the image (Set-of-Mark) | GPT-4V with marks beat fine-tuned referring models on RefCOCOg [READ, S21]. Code MIT [MEASURED, S51] | The same mark IDs serve the model (accept or reject ID 7) and the person (click mark 7). One format for both. |
| Bounding boxes on the source page screenshot | VISA highlights exact regions on document screenshots [READ, S22] | A box per counted label or symbol on the rendered sheet |
| Value-to-field references | SymGen: -20% verification time [READ, S13] | Every number in the answer links to an entity: a mark, a polygon, an IFC GlobalId, an OCR span |
| Per-item confidence colour | 26% to 58% accuracy on the hard task [READ, S12] | Green: deterministic check passed. Amber: model judgement. Red: conflict. |
| Contrastive or both-sides evidence | Mitigated overreliance [READ, S3] | "Counted 7. Also considered and rejected: 2 (crops shown)." |
| Side-by-side revisions with numbered change boxes | Stoa, Kreo, Bluebeam, STACK, Countfire all ship revision compare [READ, S26, S33, S34, S48, S42] | Pattern judges already know from Stoa's own product |
| Click a code, open the governing source at the exact location | Stoa [READ, S26]; Procore "visual previews" [READ, S36] | Click a number in the answer, zoom the sheet to the item |
| 3D check of a 2D quantity | Togal "check wall heights in 3D" [READ, S32]; Stoa stacked 3D plans [MEASURED, S31] | For IFC answers: highlight the counted elements in a 3D view |

### C. How professionals check takeoffs by hand

| Practice | Source |
|---|---|
| Manual counting with highlighters on A1 printouts, tallies in Excel | "manual counting with highlighters, measuring on A1 print outs and estimates in Excel" [READ, S44] |
| Check sheets to confirm no symbol was missed | "the check sheets reassured us that we hadn't missed any symbols" [READ, S44] |
| Every counted instance flagged on the drawing, so the estimator can audit | "every instance is flagged on the drawing so the estimator can verify the output" [READ, S43] |
| Interruptions cause double counts or missed areas in manual highlighting | [READ, S52] |
| Revisions force a full or partial recount | [READ, S43] |

The professional mental model is "one mark per item, a tick list per type, a colour per trade or per type"
[ESTIMATE from S43, S44, S32 "overlay specialty trades ... toggle each layer"]. Our evidence view should look
like a cleaned-up version of that sheet.

### D. Market: how each product shows evidence

All rows are [READ] from the vendor's own page on 2026-11-13 unless marked. Accuracy figures are vendor claims.

| Product | What it does | How it shows evidence | Accuracy or trust claim | Id |
|---|---|---|---|---|
| Togal.AI | AI takeoff: detect, measure, count, classify, compare | Quantities "for you to review"; trade overlays toggled per layer; 3D wall-height view; draw a box to find every instance | "Your estimators review, AI does the measuring" | S32 |
| Kreo | AI takeoff, auto count, scope generation | Outlines re-fitted to the drawing; added, removed, modified elements highlighted in revision compare; leader-line comments on elements; edit on drawing or report, both in sync | "lands within 94% of the real geometry" on noisy plans | S33 |
| Bluebeam Max | Premium Revu plan with AI | Smart Review finds missing sheets, missing tags, gridline issues "as AI-generated markups, dashboards, and trackable issues"; Smart Overlay; connects Revu to Claude and other AI tools | Smart Review and Overlay "in preview"; optimized for US commercial | S34 |
| Autodesk (Forma, Assistant) | AU 2026: Assistant searches inside drawings and "take[s] users directly to relevant sheets"; Drawing Change Analysis; Drawing Compliance Review (planned) | Sheet navigation; compliance issues by severity | "professional review remains part of the process" | S35 |
| Autodesk Takeoff | Takeoff product (renamed Forma Takeoff per link on construction.autodesk.com [MEASURED]) | [UNVERIFIED]: product page returned HTTP 403 | - | - |
| Procore AI | Agents for search, submittals, RFIs, contracts | "Numbered citations and visual previews show you the exact source files" | "agents never take action without sign-off" | S36 |
| Trunk Tools | Project Q&A, submittal register, bulletin changes | "Check my work with sources"; "cited answers"; highlights clouded and unclouded changes | - | S37 |
| Pelles | Plan and spec review, contradictions, DoubleCheck | "Each answer is cited to the page"; "Answers you can check at the source" | Count & Measure is beta; "keep your takeoff software" | S38 |
| Buildots | Progress tracking against plan | Progress reports vs plan (no takeoff evidence view seen) | "reduce delays by up to 50%" | S39 |
| Bild AI | Division 8 (openings, hardware) takeoff | Diff of added and deleted openings across CD sets; every opening cross-checked across plan, schedule and spec | "40-60% more bids per estimator" (one distributor) | S40 |
| Workpack (now DESTINI Takeoff) | workpack.ai redirects to destinitakeoff.com [MEASURED] | "visual markups that are easy to review, adjust, and confirm"; "Every quantity is transparent and editable" | "Numbers you can trust, explain and act on" | S41 |
| Countfire | Electrical and mechanical symbol counting | Every instance flagged on the drawing; built-in accuracy checks; check sheets | "In-built accuracy checks"; acquired by TAG Software Group | S42-S44 |
| Beam AI (ibeam.ai) | Done-for-you takeoffs | "every takeoff QA-checked before delivery" (human QA) | "99%+ accurate ... in 24-72 hours" | S45 |
| Attentive.ai | Same copy as Beam AI page [MEASURED: identical sentences] | Same | "99%+ accurate takeoffs" | S46 |
| Kojo | Procurement, AP and tool tracking for MEP contractors. Not a takeoff or drawing-QA product | Invoice-to-PO matching | - | S47 |
| STACK | Takeoff and estimating with AI auto-count | Auto-count, measurement suggestions, version overlay | "outperforms other platforms" | S48 |
| Dalux (DK), Congrid (FI) | Nordic BIM, field and quality platforms. Stoa syncs from both | No AI takeoff seen on their home pages | - | S49, S50 |
| Handoff-H1 (research, Handoff) | Agentic takeoff from blueprint PDFs | Paper reports scores, not a UI | 81.6% composite vs 77.6% estimators | S25 |

### E. Stoa

All [READ] from stoabuild.com on 2026-11-13 unless marked.

- **What it does.** "Stoa reads the drawings, specifications, contracts, schedule and site records your project
  already holds, and answers from them, with the document and page behind every sentence." [S27] It syncs
  read-only from M-Files, SharePoint, Dalux, Congrid and others [S27]. Modules: linked information, ask your
  project, outputs (work-phase plans, claims, contract review, tender requests), skills, change tracking,
  situational awareness, automations [S26].
- **How it shows evidence.** "Every sentence links to the document and page it came from, so you can check it
  before you pass it on." [S26] "Each result opens the document at the exact location." [S26] The demo answer has
  numbered citation markers, a "Where it is set out" section, a "Sources 3" list, and a "Show thought process"
  toggle [S26]. Revision compare has Plain, Wipe and Overlay modes, "Change boxes", and numbered changes each
  labelled "Read by AI" [S26]. Disclaimer under the chat: "AI can make mistakes. Verify important information."
  [S26]
- **Unknowns and honesty.** "When the documents do not hold the answer, Stoa says so." [S26] "Every AI-generated
  answer is disclosed as such and traced back to its source" for the EU AI Act [S28].
- **Accuracy claims.** Stoa publishes time and outcome figures, not accuracy: "2-8 h a week back per project
  engineer", "40% shorter from problem raised to decision made", "EUR 3M+ in mistakes caught", "EUR 4B+ of project
  value", "From design-partner interviews, July 2026" [S27]. No answer-accuracy figure was found on the site.
- **People and funding.** The site names Taavi Paananen, Co-founder and Chief Product Officer [S29]. The team
  page shows logos under "Built by a team from" and "Backed by the founders and leaders of", including Lifeline
  Ventures, Wave Ventures, Slush, Supercell, Wolt, AMD Silo AI, Nokia, McKinsey, SRV and Peikko [MEASURED from
  image alt texts, S29]. We cannot tell from the page which logo is an investor. The demo URL in the stand photo
  is demo.tahti.co [MEASURED, S31], and tahti.co redirects to stoabuild.com [MEASURED]. The host said the
  company is "still in stealth, announcing next Monday", started "three months back", and is recruiting [READ,
  S30]. **Pre-seed press: not found.** We could not run a web search, and the host says the announcement is
  pending. [UNVERIFIED]
- **What this says about judging [ESTIMATE].** Stoa already ships page-level citations and numbered change
  boxes. A text answer with a page citation will look ordinary to them. What they do not show on their site, and
  what the host asked for, is item-level evidence for a quantity (which 7 toilets), a stated method per step
  (deterministic or model), a confidence, and explicit unknowns. The evaluation is "one document at a time" with
  a series of questions, through our UI for 3D [READ, S30]. A judge will ask a question, look at the number,
  then try to confirm it on the sheet within seconds.

## Design principles for our evidence view

Each principle is tied to its evidence. Effort and priority are [ESTIMATE].

1. **Evidence first, prose last.** Show the drawing with marks before any sentence. Keep the LLM rationale
   behind a toggle, as Stoa does with "Show thought process". [S1, S3, S6, S26]
2. **Count = number of marks.** One numbered mark per counted item. The displayed count is computed from the
   marks, never typed by a model. Clicking a mark toggles it and updates the count. [S4, S21, S43, S44]
3. **Show what was not counted.** A "considered and rejected" strip with the nearest rejected candidates, and
   any conflict between two methods (detector says 7, labels say 6). [S1, S3]
4. **Two-level colour per item and per answer.** Green: a deterministic check passed. Amber: model judgement,
   not checked. Red: methods disagree. Keep the number on hover for experts. [S12, S24]
5. **Confidence as a frequency from our own held-out evaluation.** "Right 47 of 50 times on held-out questions
   of this type." Never a model's self-reported percentage. [S7, S10, S18]
6. **Short text, method label per step.** For example "Scale: read from title block 1:100 (deterministic). Room
   type WC: label OCR (deterministic). Tile area: polygon area x 1.0 (deterministic)." Long text inflates trust.
   [S7, S30]
7. **Abstain with an action.** "No scale found. Click two points of a known length, or type the scale." The
   answer recomputes on input. First person: "I could not find a scale." [S2, S23, S30]
8. **Areas and sums as an arithmetic tape.** Polygon overlay on the sheet, then a tape: room, area per room
   (computed), printed label if present, difference, total, 2% band. Each line links to its polygon. [S13, S30]
9. **Every number is a link.** Clicking a number in the answer zooms the sheet to its item, as Stoa opens a
   document "at the exact location". [S26, S36]
10. **Check every reference by machine before showing it.** A mark must lie on the sheet and inside its room
    polygon; a quote must exist in the OCR text. Unchecked references are amber or hidden. [S8, S14, S19]
11. **Match the format to the modality.** Drawing questions are visual: show the evidence on the drawing, not
    in an argument graph or a saliency heat map. [S16, S19, S20]
12. **Show the cost of each answer.** The host gave a target near EUR 0.10 per document and its questions.
    [S30]
13. **Do not force effort.** Cognitive forcing reduces overreliance but users rate it worst; site staff are
    "stubborn". Use colour to direct attention instead of mandatory steps. [S5, S30]

## What we can use this weekend

Licences below are from the GitHub API on 2026-11-13 [MEASURED, S51] unless marked. Hours are [ESTIMATE].

| Item | Use | Licence | Weights or code today | Effort |
|---|---|---|---|---|
| PDF.js (mozilla/pdf.js) | Render vector PDF pages in the starter app; get the page transform for an SVG overlay | Apache-2.0 | Yes | 2-3 h for viewer plus overlay |
| SVG overlay layer (own code, React) | Numbered marks, polygons, colour by status, click to toggle | Ours | - | 4-6 h |
| OpenSeadragon | Deep zoom for large PNG and JPEG scans with overlays | BSD-3-Clause | Yes | 2 h |
| pypdfium2 | Server-side raster at a known DPI so pixel coordinates map back to PDF coordinates | GitHub shows no single SPDX id. Check the repo licence files before use [UNVERIFIED] | Yes | 1 h |
| PyMuPDF | Alternative raster and vector path extraction | AGPL-3.0. Fine for a hackathon demo. Disclose it. Avoid it in anything Stoa would ship | Yes | 1 h |
| Set-of-Mark (microsoft/SoM) | Pattern and code for numbered marks shared by the model call and the UI | MIT (last push 2024-08-19) | Yes | 1-2 h to adapt the idea; we do not need its segmenters |
| ezdxf | DXF geometry for swiss_dwellings: polygons for the area tape | MIT | Yes | 2-3 h |
| web-ifc (ThatOpen) + three.js | IFC viewer in the browser; highlight counted elements by GlobalId | MPL-2.0 + MIT | Yes | 4-6 h |
| IfcOpenShell | Server-side IFC queries; each row cites a GlobalId | LGPL-3.0 | Yes | covered in the BIM track |
| Calibration table (own code) | Per question type and method: right/total on a held-out split, shown as "n of m" | Ours | - | 2 h once the eval harness exists |

Minimum viable evidence view [ESTIMATE, 12-16 h for one person]:

1. Answer card: value, unit, status colour, "n of m" reliability, cost, method chips per step.
2. Sheet view with numbered marks or polygons, colour by status, click to toggle, count recomputes.
3. Rejected-candidates strip and conflict banner.
4. Area tape with links to polygons.
5. Abstention card with the calibrate-scale interaction.
6. IFC ledger: one row per GlobalId, and a 3D highlight if time allows.

## What does not work

| Approach | Evidence | Verdict for us |
|---|---|---|
| Long natural-language rationales | Raise reliance on wrong answers [S1, S6]; longer text inflates confidence [S7]; below-baseline accuracy when the explanation is wrong [S3] | Hide behind a toggle. Keep to one line per step. |
| Saliency or attribution heat maps | Trust even for wrong predictions [S19]; hurt team accuracy on a hard task [S20] | Do not ship heat maps as evidence. |
| Citations alone | Random citations raise trust [S14]; 25.5% of citations in commercial engines did not support the sentence [S8] | Machine-check each reference. A page citation is not enough for a count. |
| Claim-evidence decomposition as the only safeguard | Lowered trust but not behaviour [S15] | Useful as display, not as the accuracy mechanism. |
| Argument graphs for visual reasoning | Impaired calibration on visual tasks [S16] | Not for drawings. |
| Mandatory cognitive-forcing steps | Work, but users rate them worst [S5] | Skip for a demo with site staff as the imagined user. |
| Relying on the human to fix errors | Human-AI teams below best-alone on decision tasks, g = -0.23 [S17] | The machine verifier carries accuracy. |
| Showing a raw confidence number without calibration | Calibrated uncertainty alone is "inadequate" [S18]; confidence does not raise accuracy alone [S10] | Use frequency format from our eval. |

## Open questions

1. How will Stoa score "verify in seconds"? A judge in a live session with our UI, or a rubric on screenshots?
   The host said they adapt "on the fly" and evaluate 3D through our UI [S30]. Ask at the Saturday hint.
2. Do the hidden questions include ones with no answer on the sheet? If yes, the abstention card is scored
   directly.
3. Does the colour-flag effect (S12) hold for expert estimators? S12 used lay participants. S23 suggests
   expertise changes how people react to abstention.
4. Nordic AI takeoff competitors: not verified. Without a search engine we could not find them.
5. Autodesk Takeoff and Autodesk Assistant UI details: pages returned HTTP 403 [UNVERIFIED].
6. Stoa's pre-seed round, its size and investors: not found [UNVERIFIED]. The host said an announcement comes
   "next Monday" [S30], which is about 2026-11-16 [ESTIMATE].
7. Bluebeam Max and Togal accuracy figures: none found on the pages we read.

## Check of the prior research

Source: `stoa/docs/inputs/prior-research/weekend-plan.md` (sections 2 "Verifier", "UI (Contact Sheet)", 5) and
`research-tracks.json` (track "Low-cost, verifiable agentic architectures").

| Prior claim | Check | Result |
|---|---|---|
| Kim et al. CHI 2025: explanations raise reliance on correct and incorrect answers; sources and inconsistencies reduce overreliance; N=308 | Read the paper [S1] | **Confirmed.** Added the numbers: 68.2% vs 78.2% agreement on wrong answers. The think-aloud size "n=16" was not checked. |
| Spatharioti et al. CHI 2025: colour-coded confidence improved accuracy; "roughly 50% less overreliance, not verified" | Read arXiv v2 [S12] | **Corrected.** The paper reports accuracy, not an overreliance percentage: 26% (none) vs 58% (high+low) vs 53% (low only) on the hard task, "more than doubled accuracy". Threshold: token probability <= 50% shown red. High+low was slightly slower. |
| PaperTrail CHI 2026: lowered trust, people still relied on the LLM; 26 researchers | Read abstract [S15] | **Confirmed.** |
| Ding et al. AAAI 2025: any citation, even random, raises trust; trust drops when users check | Read abstract [S14] | **Confirmed.** |
| Set-of-Mark: zero-shot GPT-4V with marks beat fine-tuned referring models on RefCOCOg | Read abstract [S21] | **Confirmed.** Code licence MIT [MEASURED]. |
| "Edit-cost" metric (He Zhang, Aug 2026) as a framing for verifiability | Not opened in this pass | **Unverified.** |
| UI "Contact Sheet": numbered marks, crops, a "not counted" row, click to toggle; area polygon with shoelace tape and 2% band; IFC ledger per GlobalId; path, tier and cost per answer | Compared with S1, S3, S4, S12, S13 and the market | **Supported.** Add: a two-level status colour per item (S12), a calibrated "n of m" frequency (S18), first-person abstention with a scale request (S2, S30), and a hidden-by-default rationale (S1, S7). |
| "Evidence and visible disagreement come first, not prose" | S1, S3, S6 | **Confirmed.** |

## Sources

Accessed 2026-11-13. "Quote" is the exact text from the page we opened. Bracketed values in quotes come from
MathML alt text in the arXiv HTML.

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2502.08554 | Fostering Appropriate Reliance on Large Language Models: The Role of Explanations, Sources, and Inconsistencies (Kim, Vaughan, Liao, Lombrozo, Russakovsky; CHI 2025) | 2025-02-12 | Sources reduce, explanations increase overreliance | "when the LLM answer is incorrect, agreement is lower when sources are provided ( [M=68.2\%] vs. [78.2\%] )"; "We find that the presence of explanations increases reliance on both correct and incorrect responses." | confirmed (68.2/78.2, N=308, pre-registered) |
| S2 | https://arxiv.org/abs/2405.00623 | "I'm Not Sure, But...": Examining the Impact of LLMs' Uncertainty Expression on User Reliance and Trust (Kim, Liao, Vorvoreanu, Ballard, Vaughan; FAccT 2024) | 2024-05-01 | First-person uncertainty lowers overreliance | "Compared to Control (80.9%), Agree is significantly lower in Uncertain1st (74.8%)."; "a greater increase in accuracy when the AI system is incorrect (43.6% to 52.0% for Uncertain1st" | confirmed (N=404) |
| S3 | https://arxiv.org/abs/2310.12558 | Large Language Models Help Humans Verify Truthfulness - Except When They Are Convincingly Wrong (Si et al.; NAACL 2024) | 2023-10-19 | Wrong explanations drive accuracy below baseline; time costs | "when the explanation is wrong, users tend to over-trust the explanations and only achieve an accuracy of [(0.35\pm 0.22)] as compared to the baseline condition [(0.49\pm 0.24)]"; "users take [2.5\pm 1.1] minutes ... [1.0\pm 0.4] minutes ... [2.7\pm 1.0] minutes" | confirmed (0.35, 0.49, 0.54; 1.01, 2.53, 2.7 min) |
| S4 | https://arxiv.org/abs/2212.06823 | Explanations Can Reduce Overreliance on AI Systems During Decision-Making (Vasconcelos et al.; CSCW 2023) | 2022-12-13 | Easy-to-check highlights reduce overreliance | "We find support for our hypotheses that there are lower levels of overreliance when provided an explanation in the form of highlights (easy to parse), as opposed to in the form of written language (hard to parse)." | confirmed (N=731) |
| S5 | https://arxiv.org/abs/2102.09692 | To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI (Buçinca, Malaya, Gajos; CSCW 2021) | 2021-02-19 | Forcing works but is disliked | "cognitive forcing significantly reduced overreliance compared to the simple explainable AI approaches. However, there was a trade-off: people assigned the least favorable subjective ratings to the designs that reduced the overreliance the most." | confirmed |
| S6 | https://arxiv.org/abs/2006.14779 | Does the Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance (Bansal et al.; CHI 2021) | 2020-06-26 | Explanations raise acceptance regardless of correctness | "explanations increased the chance that humans will accept the AI's recommendation, regardless of its correctness." | confirmed |
| S7 | https://arxiv.org/abs/2401.13835 | What Large Language Models Know and What People Think They Know (Steyvers et al.; Nature Machine Intelligence 2025) | 2024-01-24 | Humans cannot read model confidence; length inflates | "participants who view the default explanations in Experiment 1 were only slightly better than random guessing (AUC=0.589 and AUC=0.602"; "longer explanations increased user confidence, even when the extra length did not improve answer accuracy." | confirmed (AUC 0.589 and 0.602; model AUC 0.746-0.781) |
| S8 | https://arxiv.org/abs/2304.09848 | Evaluating Verifiability in Generative Search Engines (Liu, Zhang, Liang; Findings of EMNLP 2023) | 2023-04-19 | Citations often do not support the claim | "on average, a mere 51.5% of generated sentences are fully supported by citations and only 74.5% of citations support their associated sentence." | confirmed |
| S9 | https://arxiv.org/abs/2305.07722 | In Search of Verifiability: Explanations Rarely Enable Complementary Performance in AI-Advised Decision Making (Fok, Weld; AI Magazine 2024) | 2023-05-12 | Explanations matter only as verification aids | "We argue explanations are only useful to the extent that they allow a human decision maker to verify the correctness of an AI's prediction" | confirmed |
| S10 | https://arxiv.org/abs/2001.02114 | Effect of Confidence and Explanation on Accuracy and Trust Calibration in AI-Assisted Decision Making (Zhang, Liao, Bellamy; FAT* 2020) | 2020-01-07 | Confidence calibrates trust, not accuracy | "confidence score can help calibrate people's trust in an AI model, but trust calibration alone is not sufficient to improve AI-assisted decision making" | confirmed |
| S11 | https://arxiv.org/abs/2302.12389 | Explainable AI is Dead, Long Live Explainable AI! Hypothesis-driven Decision Support (Miller; FAccT 2023) | 2023-02-24 | Evaluative AI: evidence for and against | "decision support tools provide evidence for and against decisions made by people, rather than provide recommendations to accept or reject." | confirmed |
| S12 | https://arxiv.org/abs/2307.03744 (CHI 2025 version: https://doi.org/10.1145/3706598.3714082, not opened) | Comparing Traditional and LLM-based Search for Consumer Choice: A Randomized Experiment (Spatharioti, Rothschild, Goldstein, Hofman) | 2023-11-08 (v2) | Confidence colour more than doubles accuracy on the hard task | "while accuracy plummets to 26% in the control condition without any confidence highlighting, accuracy in each of the treatment conditions was substantially higher - 58% for the high + low confidence condition ... and 53% for the low confidence only condition" (dash added in place of the source's em dash) | corrected: the arXiv title differs from the published CHI 2025 paper ("Effects of LLM-based Search on Decision Making: Speed, Accuracy, and Overreliance", DOI opened via OpenAlex). Dates: v1 2023-07-07, v2 2023-11-08. 26/58/53% and the red threshold (probability <= 50%) confirmed. The paper says high+low was slightly slower (p=0.04); low-only showed no difference |
| S13 | https://arxiv.org/abs/2311.09188 | Towards Verifiable Text Generation with Symbolic References (Hennigen et al.) | 2023-11-15 (v2 2024-04-15) | Value-to-source links speed verification | "reducing the average verification time by 20%." | confirmed (20% faster; 5% more confident; 14% easier) |
| S14 | https://doi.org/10.1609/aaai.v39i22.34550 (abstract via OpenAlex API) | Citations and Trust in LLM Generated Responses (Ding et al.; AAAI 2025) | 2025 | Random citations raise trust | "We found a significant increase in trust when citations were present, a result that held true even when the citations were random" | confirmed (abstract via OpenAlex) |
| S15 | https://doi.org/10.1145/3772318.3791101 (abstract via OpenAlex API) | PaperTrail: A Claim-Evidence Interface for Grounding Provenance in LLM-based Scholarly Q&A (Martin et al.; CHI 2026) | 2026 | Lower trust, unchanged behaviour | "PaperTrail significantly lowered participants' trust compared to the baseline. However, this increased caution did not translate to behavioral changes" | confirmed (abstract via OpenAlex) |
| S16 | https://doi.org/10.1145/3830398.3830638 (abstract via OpenAlex API) | Graphionale: How Graph Visualizations of LLM Rationales Affect Human Decision Making (Wang et al.; UIST 2026) | 2026 | Graph rationales impair calibration for visual tasks | "for visual reasoning, they impair calibration yet feel more engaging and helpful." | confirmed (abstract via OpenAlex; N=204) |
| S17 | https://doi.org/10.1038/s41562-024-02024-1 (abstract via OpenAlex API) | When combinations of humans and AI are useful: A systematic review and meta-analysis (Vaccaro, Almaatouq, Malone; Nature Human Behaviour 2024) | 2024 | Human-AI combinations underperform best alone | "on average, human-AI combinations performed significantly worse than the best of humans or AI alone (Hedges' g = -0.23; 95% confidence interval, -0.39 to -0.07)." | corrected: authors are Vaccaro, Almaatouq, Malone. "Campero, Song" were wrong. Numbers (106 studies, 370 effects, g = -0.23, CI) confirmed |
| S18 | https://doi.org/10.1145/3637318 (abstract via OpenAlex API) | Designing for Appropriate Reliance: The Roles of AI Uncertainty Presentation... (Cao, Liu, Huang; CSCW 2024) | 2024 | Frequency format helps | "showing the calibrated model uncertainty alone is inadequate. Rather, calibrating model uncertainty and presenting it in a frequency format allow users to adjust their reliance accordingly" | confirmed (full title is "Designing for Appropriate Reliance: The Roles of AI Uncertainty Presentation, Initial User Decision, and Demographics in AI-Assisted Decision-Making"; frequency-format quote confirmed) |
| S19 | https://arxiv.org/abs/2112.03184 | HIVE: Evaluating the Human Interpretability of Visual Explanations (Kim et al.; ECCV 2022) | 2021-12-06 | Visual explanations build unwarranted trust | "explanations engender human trust, even for incorrect predictions, yet are not distinct enough for users to distinguish between correct and incorrect predictions." | confirmed (nearly 1000 participants) |
| S20 | https://arxiv.org/abs/2105.14944 | The effectiveness of feature attribution methods and its correlation with automatic evaluation scores (Nguyen, Kim, Nguyen; NeurIPS 2021) | 2021-05-31 | Attribution maps can hurt | "presenting attribution maps to humans does not help, but instead hurts the performance of human-AI teams compared to AI alone." | confirmed |
| S21 | https://arxiv.org/abs/2310.11441 | Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V (Yang et al.) | 2023-10-17 | Numbered marks as a shared grounding format | "overlay these regions with a set of marks e.g., alphanumerics, masks, boxes. Using the marked image as input, GPT-4V can answer the questions that require visual grounding." | confirmed (RefCOCOg in abstract) |
| S22 | https://doi.org/10.18653/v1/2025.acl-long.1456 (abstract via OpenAlex API) | VISA: Retrieval Augmented Generation with Visual Source Attribution (Ma et al.; ACL 2025) | 2025 | Boxes on document screenshots as attribution | "highlights the exact regions that support the generated answers with bounding boxes in the retrieved document screenshots." | confirmed (abstract via OpenAlex) |
| S23 | https://arxiv.org/abs/2610.27258 | The Differential Effects of AI Abstention on Advice Acceptance (Wolczynski, Liel, Saar-Tsechansky, Zalmanson) | 2026-10-19 | Abstention helps experts, not novices | "it increases advice acceptance among users with high perceived expertise and tends to decrease it among users with low perceived expertise." | confirmed |
| S24 | https://doi.org/10.48550/arxiv.2602.01264 (abstract via OpenAlex API) | Shades of Uncertainty: How AI Uncertainty Visualizations Affect Trust in Alzheimer's Predictions (Reyes et al.) | 2026-02 | Binary vs continuous encodings | "Continuous encodings improved perceived reliability and helped users recognize model limitations, while binary encodings increased momentary confidence" | confirmed (arXiv 2602.01264) |
| S25 | https://arxiv.org/abs/2608.15032 | Handoff-H1: An Orchestrated Vision-Agent System for Material Quantity Takeoff from Construction Blueprints (Chicelli et al.) | 2026-08-15 | Human estimator baseline; frontier gap | "seven frontier and open-weight models span composites of 35-61, and independent professional estimators ... post 77.6% (65.5% coverage, 87.9% P@.25)" | confirmed (10 residential sets; 35-61; 77.6%; Handoff-H1 81.6%) |
| S26 | https://stoabuild.com/product | Product, Stoa | accessed 2026-11-13 | Stoa evidence model | "Citations you can check Every sentence links to the document and page it came from, so you can check it before you pass it on."; "When the documents do not hold the answer, Stoa says so."; "Show thought process" | confirmed |
| S27 | https://stoabuild.com/ and https://stoabuild.com/case-examples | Stoa home and case examples | accessed 2026-11-13 | Product scope and outcome claims | "answers from them, with the document and page behind every sentence."; "From design-partner interviews, July 2026, and Stoa's current portfolio." | confirmed (EUR 3M+ is on /case-examples, the rest and "July 2026" on the home page) |
| S28 | https://stoabuild.com/about/security | Security, Stoa | accessed 2026-11-13 | AI Act disclosure | "Every AI-generated answer is disclosed as such and traced back to its source" | confirmed |
| S29 | https://stoabuild.com/about/team | Team, Stoa | accessed 2026-11-13 | Founder named | "Taavi Paananen · Co-founder, Chief Product Officer, Stoa" | confirmed (logo alt texts incl. Lifeline Ventures, Wave Ventures, AMD Silo AI) |
| S30 | context/stoa-drawings/2026-11-13-2308-38-conversation.md and stoa/docs/HOST.md (repo) | Stoa host talk transcript | 2026-11-13 | Host priorities on unknowns, scale, interface weight, stealth | "And then also the I don't knows are super important."; "What if you ask them to calibrate the scale?"; "How do you share sort of hypothetical parts?" | partly: quotes confirmed. The 5% UI weight was proposed by a team member; the host answered "Should be a good ballpark" (19:35-19:41) |
| S31 | stoa/docs/inputs/stoa-platform-photo.jpg (repo) | Photo of Stoa stand demo | 2026-11-13 | Demo UI and URL | Observed: URL bar "demo.tahti.co/demo-organization-2/rich-demo-data/issues"; issue panel with numbered citation chips; stacked 3D plans; Gantt with red issue markers | confirmed (photo viewed: URL, 3D plans, Gantt, issue panel) |
| S32 | https://www.togal.ai/ | Togal.AI | accessed 2026-11-13 | Review, overlays, 3D | "returns material quantities for you to review"; "Overlay multiple trades on one screen and toggle each layer on or off" | confirmed |
| S33 | https://www.kreo.net/ | Kreo | accessed 2026-11-13 | Self-check and geometry claim | "It checks its own output, re-fits every outline against the drawing, and only then hands you the result. On busy, noisy plans it lands within 94% of the real geometry." | confirmed |
| S34 | https://www.bluebeam.com/max/ | Bluebeam Max | accessed 2026-11-13 | AI markups as evidence | "See insights as AI-generated markups, dashboards, and trackable issues."; "Smart Review and Overlay are currently in preview" | confirmed (URL redirects to /bluebeam-max/) |
| S35 | https://adsknews.autodesk.com/en/news/autodesk-forma-ai-aec-connected-workflows-2026/ | How Autodesk Forma and AI are advancing a more connected future for AEC | 2026-09-15 | Assistant navigates to sheets; human review kept | "Autodesk Assistant can search inside drawings and take users directly to relevant sheets"; "while professional review remains part of the process." | confirmed (date 2026-09-15) |
| S36 | https://www.procore.com/ai | Procore AI | accessed 2026-11-13 | Numbered citations | "Numbered citations and visual previews show you the exact source files so you can verify the facts." | confirmed |
| S37 | https://trunktools.com/ | Trunk Tools | accessed 2026-11-13 | Cited answers | "Ask your project a question by text and get cited answers instantly." | confirmed |
| S38 | https://pelles.ai/ | Pelles | accessed 2026-11-13 | Page citations; takeoff not core | "Each answer is cited to the page"; "Count & Measure (beta) can check counts against a schedule, but keep your takeoff software." | confirmed |
| S39 | https://buildots.com/ | Buildots | accessed 2026-11-13 | Progress, not takeoff | "Unlock timely, accurate progress reports detailing exactly what is complete compared to your plan." | confirmed |
| S40 | https://www.bild.ai/ | Bild AI | accessed 2026-11-13 | Cross-check plan, schedule, spec | "Every opening checked across plan, schedule, and spec." | confirmed (URL redirects to d8.bild.ai/division-8) |
| S41 | https://www.workpack.ai/ (redirects to https://destinitakeoff.com/) | DESTINI Takeoff | accessed 2026-11-13 | Reviewable markups | "Instantly generate quantities with visual markups that are easy to review, adjust, and confirm." | confirmed |
| S42 | https://www.countfire.com/ | Countfire | accessed 2026-11-13 | Built-in checks | "In-built accuracy checks allow you to eliminate manual errors and have confidence in your numbers." | confirmed |
| S43 | https://www.countfire.com/blog/manual-vs-automated-electrical-takeoffs | Manual vs automated electrical takeoffs (Countfire) | accessed 2026-11-13 | Every instance flagged; vendor error-rate claim | "every instance is flagged on the drawing so the estimator can verify the output."; "error rates of 5-15% in manual takeoffs" | confirmed |
| S44 | https://www.countfire.com/blog/traditional-estimating-with-team-countfire | Team Countfire puts traditional estimating to the test (Countfire) | accessed 2026-11-13 | Manual practice: highlighters, check sheets | "manual counting with highlighters, measuring on A1 print outs and estimates in Excel."; "the check sheets reassured us that we hadn't missed any symbols" | confirmed |
| S45 | https://www.ibeam.ai/ | Beam AI | accessed 2026-11-13 | Human QA service claim | "99%+ accurate AI estimates & takeoffs in 24-72 hours"; "AI extracts quantities, with every takeoff QA-checked before delivery" | confirmed |
| S46 | https://www.attentive.ai/ | Attentive.ai | accessed 2026-11-13 | Same claim and copy | "99%+ accurate takeoffs & estimates in 24-72 hours" | confirmed (page shows "Beam AI" copy) |
| S47 | https://www.usekojo.com/ | Kojo | accessed 2026-11-13 | Procurement, not takeoff | "Control Spend. Source Smarter. Requisition Faster - All in One Platform." (dash as on page) | confirmed |
| S48 | https://www.stackct.com/ | STACK | accessed 2026-11-13 | AI auto-count and overlay | "Use auto-count and measurement suggestions so quantities take minutes, not days. Overlay drawing versions to catch every change." | confirmed |
| S49 | https://www.dalux.com/ | Dalux | accessed 2026-11-13 | Nordic BIM and field platform | "Combine all discipline models and drawings, and share it with your team on desktop or mobile." | confirmed |
| S50 | https://www.congrid.com/en/ | Congrid | accessed 2026-11-13 | Nordic quality platform, SmartCraft | "Part of the SmartCraft family, a trusted provider of software solutions for the construction industry across the UK and Nordics." | confirmed (needs a browser user agent) |
| S51 | https://api.github.com/repos/{mozilla/pdf.js, openseadragon/openseadragon, pymupdf/PyMuPDF, pypdfium2-team/pypdfium2, microsoft/SoM, mozman/ezdxf, IfcOpenShell/IfcOpenShell, ThatOpen/engine_web-ifc, mrdoob/three.js} | GitHub repository metadata | 2026-11-13 | Licences | license.spdx_id: Apache-2.0; BSD-3-Clause; AGPL-3.0; none; MIT; MIT; LGPL-3.0; MPL-2.0; MIT | confirmed (re-run with gh api; pypdfium2 has no SPDX id) |
| S52 | https://www.countfire.com/blog/interruption-culture-manual-counts | What happens to your manual counts each time you're interrupted (Countfire) | accessed 2026-11-13 | Interruptions cause manual highlighting errors | "you might find yourself absent-mindedly doing something you didn't mean to, like highlighting an area you haven't already counted." | confirmed |

## Verification

Date: 2026-11-13. Independent check by a second agent. Method: arXiv API and arXiv HTML pages for 18 papers, OpenAlex
for 7 papers without an arXiv id, direct HTTP fetch for 28 vendor and Stoa pages, `gh api` for 9 repositories,
and the repo files for S30 and S31. The harness web fetch tool was over its usage limit, so the same pages were
read by HTTP with a browser user agent.

Sources opened: 52 of 52 (S14-S16, S18, S22 and S17 by abstract through OpenAlex; S12 CHI version by DOI metadata only).
Confirmed: 49. Corrected: 2 (S12, S17). Partly: 1 (S30). Not found: 0. No finding needed the **UNVERIFIED** mark
because of a source that is not found.

Corrections:

1. S17: authors were wrong. They are Vaccaro, Almaatouq, Malone. "Campero, Song" removed. The numbers were right.
2. S12: the arXiv title is not the title of the CHI 2025 paper. The CHI paper is "Effects of LLM-based Search on
   Decision Making: Speed, Accuracy, and Overreliance". Table A and the sources row now say so. All numbers match.
3. S30 and finding 8: the 5% interface weight came from a team member. The host agreed with "Should be a good
   ballpark". The text said the host said it.
4. S18: the source title was shortened. The full title is now in the check column.

Remaining limits, not errors: the S1 think-aloud size "n=16", the "Edit-cost" metric (He Zhang, Aug 2026), the Autodesk
Takeoff page and the Stoa pre-seed round were not checked. Marketing figures (S33, S43, S45, S46) are vendor claims,
and the report already labels them so. The S3 "80 crowdworkers", S5 "N=199" and S2 "pre-registered" details in
table A were not re-checked against the full text, except N=404 and N=731 which were.
