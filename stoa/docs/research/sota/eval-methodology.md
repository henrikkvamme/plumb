# Evaluation methodology: predicting the hidden-test score

Track: how to build an evaluation environment that predicts our score on Stoa's hidden test set.
Written 2026-11-13. Every source was opened on that date. S22 was confirmed through its Crossref record because the publisher page returned 403. See "Verification" at the end.

Labels in this file:

- **MEASURED**: we computed it on `stoa/data/junction-dataset/questions.jsonl` today. The scripts are in the
  session scratchpad. They are small enough to rewrite (about 30 lines each).
- **SOURCE**: a paper, a repository or a document says it. The source id points to the table at the end.
- **ESTIMATE**: our own reasoning or arithmetic with assumed inputs. Never treat it as a measurement.

## Findings that change decisions

1. **Distribution shift, not test-set reuse, is the main danger.** In more than 100 Kaggle competitions, public
   and private scores agreed well. The outliers had non-i.i.d. splits or small test sets. The authors say
   distribution shift "may be a more pressing problem than test set re-use" [S2]. Decision: spend harness effort
   on splits that imitate the shift to the hidden set (new templates, languages, sources, formats), not on
   rationing looks at a random holdout. Moves accuracy on the hidden set.
2. **Split by group, and report the worst group.** WILDS shows that standard training gives "substantially
   lower out-of-distribution than in-distribution performance" on every dataset [S7]. A random question split
   puts the same drawing and the same template on both sides. Our proxy hidden sets must hold out whole
   drawings, whole templates, whole languages, whole IFC projects and whole sources. The headline number is the
   worst of these splits, not the mean.
3. **Error bars must be clustered by drawing, and comparisons must be paired.** MEASURED: on cubicasa5k, the
   template-mode baseline (55.32%, which reproduces the lead's 55.3%) has a clustered standard error 1.88 times
   the naive one, because each drawing carries about 18 questions. SOURCE: clustered errors "can be over 3X
   larger" and paired differences are "a free reduction in estimator variance" [S19]. ESTIMATE: with a
   100-drawing cubicasa holdout, two systems must differ by about 4 points before we can trust the
   difference; on ifc_bench (820 questions on 25 models) about 12 points; on opening_design (64 questions on
   3 sheets) no realistic change is detectable. Decision: never accept a change on a small source from the mean
   alone. Read the per-question flips.
4. **Blind and prior baselines are mandatory.** VQA models collapse when answer priors change between train
   and test [S12]. Frontier models answer many "visual" questions with no image (GeminiPro 42.9% on MMMU
   without images) [S13]. MEASURED: a mode guess per template already gives 55.3% on cubicasa5k. Decision: the
   harness reports every system next to (a) the template-mode baseline and (b) a blind LLM that sees only the
   question. Report "gain over the prior baseline" per template. A hidden set with other answer distributions
   removes the prior gain, so a gain that comes from priors does not transfer.
5. **Score abstention explicitly, with more than one cost.** Effective reliability gives +1 for a correct
   answer, -c for a wrong answer and 0 for an abstention, with c in {1, 10, 100} [S14]. A recent OpenAI paper
   argues that binary grading rewards guessing and proposes a confidence target t, with a penalty of
   t/(1-t) for a wrong answer [S16]. Reasoning fine-tuning made abstention worse by 24% on average in 20
   frontier LLMs [S17]. We do not know Stoa's rule (open question 1). Decision: report accuracy with
   abstain-as-wrong, and also Phi_1 and Phi_10, and the full risk-coverage curve. Choose the threshold for the
   rule that Stoa confirms.
6. **An LLM judge for free text needs a reference answer and a human check.** Judges agree with experts mainly
   on questions they can answer themselves; expert references "largely" fix this [S24]. Judges are lenient, and
   high percent agreement can hide very different scores [S23]. Decision: for ifc_bench, extract numbers and
   units deterministically first, and send only the rest to a judge that sees the reference. Validate the judge
   on about 60 hand-labelled answers and report Cohen's kappa, not percent agreement.
7. **Cache and replay every model call; temperature 0 is not deterministic.** One provider test got 80
   distinct completions from 1,000 identical temperature-0 requests [S30]. Across 5 LLMs, run-to-run accuracy
   varied up to 15% [S31]. Decision: key a disk cache on (pinned model id, full request, config), commit the run
   manifest, and compare systems on replayed outputs. Re-run with fresh calls only to measure variance.
8. **A custom harness of a few hundred lines is the right size.** Our scoring is domain-specific: 2% tolerance,
   clustering by drawing, per-template and per-split reports, precompute cost per drawing. Inspect AI (MIT,
   0.3.289 released 2026-11-10) has a good cache design and a log viewer [S32, S33], but our metrics would
   still be custom code. Decision: write our own core (about 4 to 6 hours, ESTIMATE). Copy Inspect's cache-key
   design.
9. **Metamorphic tests catch failures that accuracy hides.** Under a 180-degree rotation of chess positions, at
   most 10.6% of 500 pairs got consistent evaluations from frontier LLMs [S41]. DeepTest found thousands of
   wrong outputs under rain, fog and blur [S40]. Decision: the harness runs rotation, flip, rescale,
   re-rasterisation, JPEG and scan-noise variants, and format swaps (PDF vs PNG vs DXF of the same Swiss
   floor). It reports the answer-change rate. This is our best proxy for "tricky drawings" in the hidden set,
   and it needs no new labels.
10. **Score the evidence, not only the answer.** In CiteVQA, the best of 20 multimodal models reaches only 76.0
    Strict Attributed Accuracy (answer and cited box both right), and models "frequently produce the right
    answer while citing the wrong region" [S45]. People rely less on wrong answers when sources are shown,
    but explanations alone raise reliance on wrong answers too [S49]. Decision: add a "verifiable accuracy"
    metric: correct answer AND evidence that matches ground-truth objects (count marks vs CubiCasa SVG objects,
    area polygons vs Swiss DXF rooms). This moves the 25% verification criterion with a number.

## Landscape

### 1. Benchmark overfitting and adaptive overfitting

| Evidence | What it shows | SOURCE |
|---|---|---|
| ImageNetV2, CIFAR-10.1 | New test sets from the same process: accuracy drops 3-15% (CIFAR-10) and 11-14% (ImageNet). The authors attribute the drop to "slightly harder" images, not to adaptivity. | S1 |
| Kaggle meta-analysis, 100+ competitions | "little evidence of substantial overfitting". Outliers: non-i.i.d. splits, small test sets. Distribution shift matters more than reuse. | S2 |
| Ladder mechanism | Show a new score only if it beats the best by more than a step eta, rounded to eta. Parameter-free variant uses a paired t-test. Resists leaderboard attacks. | S3 |
| Reusable holdout | "Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself." Differential privacy and description-length methods bound it. | S4 |
| Chatbot Arena | Private testing of many variants (27 by Meta before Llama-4) and selective disclosure bias the scores toward "Arena-specific dynamics". | S5 |
| GSM1k | Fresh copy of GSM8k: drops up to 8% for some model families, linked to memorisation. Frontier models showed little overfitting. | S6 |

What this means for us:

- Our risk has two parts. The first part is adaptive overfitting: about 50 decisions in 36 hours on the same
  public questions. S2 says this effect is usually small (in its top-submission plots the deviation is about 1%). The second part is the shift to a
  harder hidden set: S1 shows drops of 3-15% (CIFAR-10) and 11-14% (ImageNet) even on new test sets from the same process, and S2 says shift is the more pressing problem (it gives no size). Spend effort in that ratio.
- The Ladder idea fits our workflow: accept a change into `main` only when the paired, clustered improvement on
  the dev splits is above a threshold. Otherwise keep the old score as the reference. This blocks the slow
  climb from accepting noise.
- Keep a locked final split (see checklist). Look at it at most 3 times: once now as a baseline, once on
  Saturday evening, once at the freeze.
- S5 is a warning against "private testing" inside the team: if five people each try variants and keep the best,
  the reported number is biased upwards by selection. The harness logs every run, also the bad ones.

### 2. Distribution shift evaluation

| Method | Idea | Limit | SOURCE |
|---|---|---|---|
| Grouped splits, leave-one-domain-out (WILDS) | Test domains not seen in training. Report out-of-distribution and worst-group metrics. | Needs domain labels. Our domains: source, template, language, format, project. | S7 |
| Model selection under shift (DomainBed) | Algorithms without a model-selection rule are "incomplete". Careful ERM matches special methods. | Choosing thresholds on the in-distribution split is itself a shift risk. | S8 |
| Accuracy on the line | OOD accuracy correlates strongly with ID accuracy across many models. | Weaker for some shifts (CIFAR-10-C, Camelyon17). | S9 |
| Agreement on the line | OOD agreement between two models tracks ID agreement, so OOD accuracy can be predicted with no labels. | Holds only where accuracy-on-the-line holds. Designed for classifiers. | S10 |
| Average Thresholded Confidence (ATC) | Learn a confidence threshold on labelled data; predicted OOD accuracy = fraction of unlabelled items above it. 2-4x better than earlier methods. | Proven impossible in general: efficacy "rests upon (perhaps unstated) assumptions on the nature of the shift". | S11 |

What this means for us:

- We have about 6,570 historic scans with no questions (lead's figure). ATC and agreement-based estimates are
  the only label-free tools. ESTIMATE: they are weak for us, because (a) our pipeline is not one classifier,
  (b) the scans differ in kind (hand-drawn, old, no scale), and S11 proves no method works without shift
  assumptions. Use them only as a sanity check: if two of our systems disagree on 40% of historic-scan counts
  but on 5% of cubicasa counts, the hidden-set accuracy on scans is low, whatever the public score says.
- Better: label a small set ourselves (see checklist). Fifty to one hundred questions on habs, finna,
  europeana and wikimedia drawings, double-labelled, is worth more than any label-free estimator.

### 3. Shortcut and prior baselines in VQA

| Baseline | What it measures | SOURCE |
|---|---|---|
| Answer prior per question type (VQA-CP) | Train and test priors differ per question type; models "degrade significantly". | S12 |
| Blind LLM (MMStar) | Answer from text only. GeminiPro 42.9% on MMMU without images. MMStar proposes metrics for leakage and multimodal gain. | S13 |
| Low-level vision probes (BlindTest) | Four VLMs averaged 58.07% on simple tasks such as counting line crossings. | S50 |

What this means for us: the hidden set may change answer distributions (other cities, other building sizes).
Two diagnostics are cheap. (a) Gain over template mode, per template. (b) A changed-prior split: put the
drawings with rare answers for a template (for example 4 or more bathrooms) into a separate split and report
it. A system that leans on priors fails there.

### 4. Selective prediction and abstention

| Metric | Definition | Note | SOURCE |
|---|---|---|---|
| Coverage and risk | Coverage = share answered; risk = error on that share. | At 1% risk, VQA v2 models answered under 7.5% of questions with softmax confidence. | S14 |
| Effective reliability Phi_c | +Acc if answered and correct, -c if answered and wrong, 0 if abstained; c = 1, 10, 100. | Threshold chosen on validation to maximise Phi_c. | S14 |
| AURC vs AUGRC | Area under the generalised risk-coverage curve = average risk of undetected failures. | Changed metric rankings on 5 of 6 datasets compared with current approaches. | S15 |
| Confidence target t | Instruction: answer only if more than t confident; wrong answers cost t/(1-t). | Answering beats abstaining only when P(correct) > t. | S16 |
| AbstentionBench | 20 frontier LLMs; scaling helps little; reasoning tuning hurts abstention by 24%. | Do not trust a reasoning model's own "I am not sure". | S17 |
| Conformal prediction | Prediction sets with "explicit, non-asymptotic guarantees" without model assumptions. | The guarantee needs calibration data like the test data (exchangeability; standard theory, not quoted from S18). Under shift the coverage can fail. | S18 |

Calibration for counts (ESTIMATE, design): a count is right or wrong, so treat the confidence as P(exact).
Report a reliability table per source (10 bins: mean confidence vs exact-match rate) and the Brier score. For a
human, also show an interval ("11 to 13") from conformal residuals on the dev split, and say it is
calibrated on public data only. Compute confidence from evidence signals that do not come from the LLM's
self-report: agreement between two witnesses (detector and LLM, DXF and PDF), metamorphic stability, detector
scores. S17 supports this choice.

### 5. Statistics for comparing two systems on the same questions

| Tool | Use | SOURCE |
|---|---|---|
| Clustered standard errors | Questions in groups (drawings); naive errors are inconsistent; up to 3x larger. | S19 |
| Paired differences | Same questions for both systems; lower variance when scores correlate. | S19 |
| Power, minimum detectable effect | delta = (z_a/2 + z_b) * sqrt(var / n); worked example suggests 1,000+ questions for a new eval. | S19 |
| Power in NLP | Underpowered comparisons are common; 2,000 MT sentences give about 75% power for 1 BLEU. | S20 |
| Test selection protocol | Significance testing is "often ignored or misused" in NLP; gives a selection protocol. | S21 |
| McNemar test | Classic paired test on discordant pairs. Dietterich 1998 recommends it for one test set. | S22 (publisher page returned 403; confirmed through Crossref) |

MEASURED group sizes (questions per drawing; grouping by file stem, and by project prefix for ifc_models):

| source | questions | groups | questions per group (mean / median / max) | distinct question strings |
|---|---|---|---|---|
| cubicasa5k | 85,514 | 4,787 drawings | 17.86 / 18 / 24 | 24 |
| swiss_dwellings | 37,584 | 1,040 floors | 36.14 / 36 / 44 | 3,147 |
| ifc_models | 3,062 | 84 files, 29 model stems, 16 projects | 36.45 / 24 / 280 per file | 2,853 |
| ifc_bench | 820 | 25 models | 32.8 / 35 / 64 | 701 |
| opening_design | 64 | 3 sheets | 21.3 / 20 / 41 | 64 |

MEASURED design effect: the cubicasa5k template-mode baseline has naive SE 0.00170 and cluster-robust SE
0.00319 (ratio 1.88, variance ratio about 3.5). We did not compute this for swiss_dwellings or ifc_models:
their question strings include file names, so a per-string mode leaks the answer and the baseline is invalid.

ESTIMATE of the minimum detectable effect (paired, alpha 0.05, power 0.8, MDE = 2.8 * sqrt(d * DEFF / n),
d = share of questions where the two systems disagree, DEFF = variance inflation; only cubicasa's DEFF is
measured, the others are guesses):

| split | n | assumed d | assumed DEFF | MDE (points) |
|---|---|---|---|---|
| cubicasa, 500-drawing holdout | 9,000 | 0.10 | 3.5 (measured) | 1.7 |
| cubicasa, 100-drawing holdout | 1,800 | 0.10 | 3.5 (measured) | 3.9 |
| swiss, 200-floor holdout | 7,200 | 0.10 | 5.9 | 2.5 |
| ifc_models, all | 3,062 | 0.15 | 7.7 | 5.4 |
| ifc_bench, all | 820 | 0.20 | 7.7 | 12.1 |
| opening_design, all | 64 | 0.25 | 4 | 35 |

Why per-question flips matter more than the mean: two systems at 80% can disagree on 20% of questions. The mean
hides that. The flip table (wins, losses, by template and source) shows (a) whether a change fixes one template
and breaks another, which predicts fragility on a hidden set with other templates, and (b) the McNemar input
(the discordant counts). Use the cluster bootstrap for the confidence interval: resample drawings with
replacement, keep all questions of a drawing together, recompute the paired difference, 2,000 resamples.

### 6. Scoring free-text answers

| Finding | SOURCE |
|---|---|
| Only the largest judges reach "reasonable alignment"; still behind humans; up to 5 points off; lenient; high percent agreement can hide very different scores. Short-answer QA setting. GEM 2025. | S23 |
| Without a reference, judges agree with experts mainly on questions they solve themselves; expert references "largely" fix this. | S24 |
| A 2026 study reported a 33-41 point gap between raw agreement and kappa and position bias in production judges. It was **withdrawn** by arXiv for quality. Do not cite its numbers. | S25 |

Rubric design for ifc_bench (ESTIMATE, design):

1. Parse the reference: numbers with units, IFC class names, GlobalIds, names, yes/no.
2. Parse the candidate the same way. Normalise units (m2, sq m, m², ft²), decimal commas, thousands separators.
3. Deterministic verdict when the reference has a number: correct if within 2% (as for areas); for counts,
   exact. For lists of ids: set precision and recall.
4. Only when no deterministic rule applies: a judge prompt with question, reference, candidate, and a
   three-way output (correct, incorrect, abstained). Pin the judge model, cache its outputs.
5. Validate the judge on about 60 items labelled by two team members. Report Cohen's kappa against each human
   and between the humans.

### 7. Label noise

| Finding | SOURCE |
|---|---|
| At least 3.3% label errors on average in 10 test sets; 6% in ImageNet val; a 6% shift in mislabelled prevalence can reverse a model ranking. | S26 |
| "Platinum" benchmarks: curated to remove label errors; frontier LLMs still fail simple tasks. | S27 |
| 6.49% of MMLU questions have errors; 57% in the analysed Virology subset. | S28 |
| cleanlab (Apache-2.0) finds likely label errors from model predictions. | S29 |

What this means for us: CubiCasa labels are known to be noisy (prior research says so; not verified here). Our
ceiling is below 100%. Procedure (ESTIMATE): sample 100 questions where our best system and the reference
disagree, stratified by template; two people judge each from the drawing. The share where the reference is
wrong estimates the noise rate in the disagreement set. Then (a) report accuracy against the reference (what
Stoa scores) and (b) a "corrected" accuracy, and (c) never tune toward a template whose disagreements are
mostly label errors. That would fit noise that the hidden set may not share.

### 8. Reproducible LLM evaluation

| Finding | SOURCE |
|---|---|
| Temperature 0 is not deterministic: 80 distinct completions in 1,000; cause is batch-size dependence in kernels. | S30 |
| Five "deterministic" LLMs varied up to 15% in accuracy across 10 runs. | S31 |
| Inspect cache key: model name and base URL, message history, epoch, generation config, tools. Default expiry one week; `None` never expires. Use a versioned model name. | S33 |
| Claude prices today (per million tokens): Opus 5.5 $4 in / $20 out, Sonnet 5.5 $2 / $10, cache hits $0.20 and $0.10; Batch API 50% off input and output. | S38 |

Cost accounting per question (ESTIMATE, design): record for each answer the input, output and cached tokens
per model, GPU seconds and CPU seconds. Cost = tokens times the price table (pinned in the manifest) + GPU
seconds times the hourly rate. Record precompute per drawing separately and amortise it over the questions on
that drawing. MEASURED: cubicasa5k carries 17.86 questions per drawing and swiss_dwellings 36.14, so a hidden
set with fewer questions per drawing raises the per-question cost. Report both "amortised" and "cold" (one
question per drawing) cost, and p50 and p95 latency.

### 9. Harness tools

| Tool | Licence | State today | Fit for us | SOURCE |
|---|---|---|---|---|
| Inspect AI (UK AI Security Institute) | MIT | 0.3.289, released 2026-11-10; cache, log viewer, model-graded scorers | Good design to copy. Its unit is a sample with one model call chain; our multi-format pipeline and clustered statistics would be custom. | S32, S33 |
| promptfoo | MIT | Being acquired by OpenAI (announced 2026-03-09); stays open source | Prompt and red-team tests, YAML. Weak fit for numeric 2% scoring and grouped statistics. | S34 |
| OpenAI evals | MIT | README points to "Evals directly in the OpenAI Dashboard"; no custom-code evals accepted | Not a fit. | S35 |
| Braintrust autoevals | MIT | Library with a "Numeric difference" scorer; the platform is SaaS | Could reuse scorers; the platform is not needed. | S36 |
| LangSmith | SaaS | Free plan: 1 seat, 5k traces per month, 14-day retention | Too small for 127k questions; one seat. | S37 |
| Hypothesis | MPL-2.0 (PyPI) | "The property-based testing library for Python" | Use for metamorphic and property tests of parsers and geometry. | S43 |
| pytest plus a JSONL runner | MIT (pytest, PyPI) | | The core of a custom harness. | - |

Recommendation (ESTIMATE): a custom runner of 300 to 600 lines. Reasons: (a) our scorer, splits and statistics
are domain code in any tool; (b) we need per-drawing precompute and cost amortisation, which no tool models;
(c) a 36-hour team cannot absorb a framework's concepts. Copy two ideas: Inspect's cache key (S33) and its
log-per-run design.

### 10. Metamorphic and property-based testing

| Evidence | SOURCE |
|---|---|
| CheckList: a matrix of capabilities and test types; users found almost 3 times as many bugs. Test types include invariance and directional expectation. | S39 |
| DeepTest: realistic image transformations found thousands of wrong outputs in driving models. | S40 |
| Chess positions rotated 180 degrees: at most 10.6% of 500 pairs consistent; averages over answered pairs hid most failures. | S41 |
| MetaRA (2026): metamorphic relations for multimodal VQA expose "over-reliance on superficial visual cues". | S42 |

Metamorphic relations for drawings (ESTIMATE, design; each needs no new labels):

- Invariance: rotate 90/180/270, mirror, rescale 0.5x and 2x, crop margins, re-render the PDF at another DPI,
  JPEG at quality 40, add scan noise and skew, convert to greyscale. Counts and areas must not change (areas
  change only when the scale bar or the dimension text is lost: then the right output is "I do not know").
- Format swap: the same Swiss floor as PDF, PNG and DXF must give the same answers.
- Language swap: the English and local-language twin of a question must give the same answer. MEASURED fact
  from the lead: templates come in pairs, so this test is free.
- Directional: erase one door symbol (inpaint), the door count must drop by one. Remove the scale bar and the
  dimension text, the area answer must become an abstention.
- Report: the answer-change rate per relation, and accuracy on the transformed set.

### 11. Evidence quality

| Method | Definition | SOURCE |
|---|---|---|
| Pointing game | "A hit is counted if the maximum point lies on one of the annotated instances"; Acc = hits / (hits + misses). Also report a difficult subset; a center-point baseline. | S44 |
| Strict attributed accuracy (CiteVQA) | Credit only when answer and cited region are both correct. Best model 76.0; best open model 22.5. | S45 |
| Citation recall and precision | 51.5% of generated sentences fully supported; 74.5% of citations support their sentence (4 search engines). | S46 |
| Verifiability theory | Explanations help only when they let a person verify the prediction; many tasks do not allow easy verification. | S47 |
| Cost of verification | People choose whether to check; explanations reduce overreliance when they lower the cost of checking (N = 731). | S48 |
| Sources and inconsistencies | Explanations raise reliance on right and wrong answers; sources and visible inconsistencies reduce reliance on wrong answers (N = 308, CHI 2025). | S49 |

Metrics for our evidence (ESTIMATE, design):

- Count marks: match predicted points to ground-truth object positions (CubiCasa SVG objects; Swiss DXF
  entities) with the Hungarian algorithm and a radius, then report mark precision and recall. A correct count
  with wrong marks is "right for the wrong reason": count it as unverifiable.
- Areas: IoU of the predicted polygon against the DXF room polygon, plus the share of answers where the printed
  label and the computed area agree.
- IFC: the cited GlobalIds must exist and their quantities must sum to the answer (a deterministic check).
- Human check time: a timed test with 3 team members on 30 answers each, with and without the evidence view.
  Record seconds to a verdict and the share of planted wrong answers they catch. S48 and S49 say the second
  number matters most: evidence must make wrong answers visible, not only look convincing.

## What we can use this weekend

| Item | What | Licence | Effort (ESTIMATE) |
|---|---|---|---|
| Custom runner (Python, `stoa/<app>/py/eval/` per repo rules) | JSONL in, run manifest out, scorers, splits, reports | ours | 4-6 h core, 2 h reports |
| Split builder | Deterministic hash of group key to fold; leave-one-template-out, leave-one-language-out, leave-one-source-out, leave-one-project-out (IFC), changed-prior split | ours | 1.5 h |
| Cluster bootstrap and McNemar | numpy; resample drawings | BSD (numpy) | 1 h |
| Model-call cache | SQLite or files keyed by sha256(model id, request JSON, config); replay mode fails on a miss | ours | 1 h |
| Free-text scorer | Number and unit extraction, 2% rule, judge only on residue, kappa on 60 labels | ours | 3 h incl. labelling |
| Metamorphic set | Pillow and OpenCV transforms; pymupdf re-render at other DPI | Pillow (MIT-CMU, formerly called HPND), OpenCV (Apache-2.0), PyMuPDF (AGPL-3.0 or paid Artifex licence, per PyPI) | 2-3 h |
| Label-noise audit | 100 disagreements, two labellers | - | 2 h of people time |
| Historic-scan mini set | 60-100 questions on habs, finna, europeana, wikimedia, double-labelled, incl. "needs scale" items | per file, see each LICENSE.md | 3 h of people time |
| cleanlab | Rank likely label errors | Apache-2.0 | optional, 1 h |
| Inspect AI | Only if we want its log viewer | MIT | skip |

Commands we expect (ESTIMATE, names are proposals):

```sh
python -m eval run --system <name> --split dev --replay      # cached outputs only, free, deterministic
python -m eval run --system <name> --split dev --live        # new calls, writes cache
python -m eval compare runs/<a> runs/<b>                     # paired clustered CI, McNemar, flip table
python -m eval report runs/<a> --by source,template,language # worst group first
python -m eval meta runs/<a> --relations rot90,flip,dpi,jpeg,format
```

## What does not work

- **Random question splits.** Same drawing and same template on both sides. MEASURED: cubicasa5k has only
  24 question strings, so every test question has a training twin. Prior research measured that template
  signatures recur in 92-100% of held-out questions for the three big sources under a drawing split (not
  re-run by us; consistent with our distinct-string counts). A drawing split alone therefore says nothing
  about new templates.
- **Naive standard errors.** Too small by 1.88x on cubicasa5k (MEASURED) and up to 3x elsewhere [S19].
- **Percent agreement for a judge.** Can hide large score differences [S23].
- **A judge without a reference** on questions it cannot solve [S24].
- **Trusting temperature 0 for reproducibility** [S30, S31].
- **The LLM's self-reported confidence as the abstention signal**, especially from reasoning models [S17].
- **Label-free OOD accuracy estimates as a target.** No method works without shift assumptions [S11]. Use
  them as a warning light only.
- **AURC alone to rank abstention policies.** Fails requirements set out in S15; use AUGRC and fixed-cost
  Phi_c.
- **The mean over answered questions.** Hides abstentions and failures [S41]. Always report coverage.
- **Tuning on the 64 opening_design questions.** ESTIMATE: an MDE of about 35 points means any change there is
  noise.
- **SaaS harnesses with small free tiers** (LangSmith: 5k traces per month, 1 seat [S37]).

## Open questions

1. How does Stoa score an abstention: as wrong, as zero, or with a penalty? This sets the threshold (Finding 5).
2. How does Stoa score free text (ifc_bench): an LLM judge, which model, which rubric?
3. Does the hidden set reuse public drawings with new questions, or use new drawings? The answer decides
   whether drawing-level precompute can be cached and whether a leave-drawing-out split is enough.
4. Does inference cost include one-off precompute per drawing and GPU time?
5. What share of the hidden set is on historic scans with no public questions? Our mini set would then deserve
   a larger weight in the headline number.
6. Our design effects for swiss_dwellings and ifc_models are not measured yet. Measure them on the first real
   system run.

## Check of the prior research

Checked against `stoa/docs/inputs/prior-research/weekend-plan.md` and `research-tracks.json`, on the
evaluation topic only.

| Prior claim | Verdict |
|---|---|
| "Split by drawing, never by question." | Confirmed, but not enough. Also hold out templates, languages, sources and IFC projects (S2, S7). |
| "Test: the 241 preview drawings. None is in training. Report per template." | Partly right. The preview is a subset of the public set, so it imitates the public distribution, not the hidden one. Add the grouped splits and the metamorphic set. |
| "Exact template lookup already covers 95.0% of held-out preview questions (measured)." | Not re-run. It is an in-distribution figure under a drawing split. It does not predict coverage on new templates; the hidden set can have other templates (brief). Its own per-source numbers (ifc_bench 3.2%) show the drop. |
| "Swiss rules already score about 97%" ... "fitted on the same 65 floors". | In-sample. The plan says so itself. Treat 97% as an upper bound until measured on held-out floors. |
| "If the judge does not raise held-out accuracy, we do not call it." | Good rule. Add: decide with a paired, clustered test, not a mean difference (S19). |
| "ifc_bench agent with a Haiku judge copied from the cobbie rubric." | Risky as stated. Give the judge the reference, extract numbers deterministically first, and validate it on hand labels with kappa (S23, S24). |
| "The detector count must not change under flip and rotation." | Confirmed as a sound check (S40, S41). Extend it to a harness-wide metamorphic suite. |
| "CubiCasa labels are noisy, so some reference answers are wrong." | Plausible (S26 shows test-set noise is common), not verified for CubiCasa here. Measure it with the 100-item audit. |
| CHI 2025 citation (2502.08554): "sources and visible inconsistencies reduce overreliance, and explanations increase it." | Confirmed from the abstract [S49]. Precisely: explanations increase reliance on both correct and incorrect answers. |
| Cost "under $0.005 per question blended". | Not checked here. Note that it depends on about 18 to 36 questions per drawing (MEASURED). A hidden set with fewer questions per drawing raises it. |

## Checklist for our harness

Data and splits

- [ ] Group key per question: drawing stem (all formats of one drawing share it); IFC project prefix for
      ifc_models; model for ifc_bench.
- [ ] Template id per question (normalise the file name and numbers out of the string), language id, source.
- [ ] Fold assignment by a fixed hash of the group key. Never by row.
- [ ] Splits: `dev` (drawing holdout), `lot` (leave-one-template-out, per template pair), `lol`
      (leave-one-language-out), `los` (leave-one-source-out, for any learned or tuned component),
      `prior` (rare-answer drawings), `meta` (metamorphic variants), `scan` (our hand-labelled historic set).
- [ ] `final`: a locked 10% of drawings per source, stratified. At most 3 looks, each logged.
- [ ] Headline = worst of `dev`, `lot`, `lol`, `scan`, weighted by expected hidden-set share. Also show each.

Scoring

- [ ] Count exact; area, length, volume within 2%; free text by the deterministic-then-judge scorer.
- [ ] Every answer carries: value, unit, confidence in [0, 1], abstain flag, abstain reason (for example
      "no scale"), evidence object.
- [ ] Report accuracy (abstain = wrong), coverage, Phi_1, Phi_10, AUGRC, risk-coverage curve, reliability
      table, Brier score.
- [ ] Report gain over template-mode and over a blind LLM, per template.
- [ ] Evidence metrics: mark precision and recall against ground-truth objects, polygon IoU, cited-id check,
      "verifiable accuracy".
- [ ] Label-noise audit result shown next to the accuracy.

Statistics

- [ ] Cluster bootstrap by group (2,000 resamples) for every number.
- [ ] `compare`: paired difference with CI, McNemar on discordant pairs, flip table by template and source.
- [ ] Accept rule (Ladder-style): accept a change only if the paired clustered lower bound is above 0 on the
      worst split and no template loses more than its MDE.
- [ ] Print the MDE next to every split, so nobody reads noise as progress.

Reproducibility and cost

- [ ] Model-call cache keyed by pinned model id, request, config; replay mode fails on a cache miss.
- [ ] Run manifest: git SHA, dirty flag, system config, model ids, price table, split hashes, seed, start and
      end time, machine.
- [ ] Every run is logged, also failed and abandoned ones (no private testing, S5).
- [ ] Per answer: tokens per model, cached tokens, GPU seconds, CPU seconds, latency. Precompute per drawing
      logged apart and amortised. Report amortised and cold cost, p50 and p95 latency.
- [ ] Variance check: one live re-run of the final system to measure run-to-run spread.

Tests

- [ ] Hypothesis or pytest property tests for parsers (numbers, units, decimal commas) and geometry
      (shoelace area, unit conversion).
- [ ] Metamorphic suite with the answer-change rate per relation.
- [ ] Golden tests: 20 hand-checked questions per source that must never regress.

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/1902.10811 | Do ImageNet Classifiers Generalize to ImageNet? (Recht, Roelofs, Schmidt, Shankar) | 2019-02 | New test sets drop accuracy; not adaptivity | "We evaluate a broad range of models and find accuracy drops of 3% - 15% on CIFAR-10 and 11% - 14% on ImageNet." | confirmed |
| S2 | https://papers.nips.cc/paper/2019/hash/ee39e503b6bedf0c98c388b7e8589aca-Abstract.html | A Meta-Analysis of Overfitting in Machine Learning (Roelofs et al.), NeurIPS 2019 | 2019 | Little overfitting on Kaggle; shift matters more | "a non-i.i.d. split lead to substantial gaps between public and private scores, suggesting that distribution shifts [...] may be a more pressing problem than test set re-use" (PDF, Section 5); abstract: "little evidence of substantial overfitting" | confirmed (abstract and PDF; 120 competitions, "over one hundred") |
| S3 | https://arxiv.org/abs/1502.04585 | The Ladder: A Reliable Leaderboard for Machine Learning Competitions (Blum, Hardt) | 2015-02 | Ladder mechanism | "If the estimate is below the previous best by some margin, it releases the estimate and updates the best estimate." | confirmed |
| S4 | https://arxiv.org/abs/1506.02629 | Generalization in Adaptive Data Analysis and Holdout Reuse (Dwork et al.) | 2015-06 | Holdout reuse overfits | "Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself." | confirmed |
| S5 | https://arxiv.org/abs/2504.20879 | The Leaderboard Illusion (Singh et al.) | 2025-04 | Private testing and selective disclosure bias scores | "leads to biased Arena scores due to selective disclosure of performance results" | confirmed |
| S6 | https://arxiv.org/abs/2405.00332 | A Careful Examination of LLM Performance on Grade School Arithmetic (Zhang et al.) | 2024-05 | Fresh test copy reveals overfitting in some families | "we observe accuracy drops of up to 8%, with several families of models showing evidence of systematic overfitting" | confirmed |
| S7 | https://arxiv.org/abs/2012.07421 | WILDS: A Benchmark of in-the-Wild Distribution Shifts (Koh et al.) | 2020-12 | OOD below ID under domain splits | "standard training yields substantially lower out-of-distribution than in-distribution performance" | confirmed |
| S8 | https://arxiv.org/abs/2007.01434 | In Search of Lost Domain Generalization (Gulrajani, Lopez-Paz) | 2020-07 | Model selection under shift | "domain generalization algorithms without a model selection strategy should be regarded as incomplete" | confirmed |
| S9 | https://arxiv.org/abs/2107.04649 | Accuracy on the Line (Miller et al.) | 2021-07 | ID and OOD accuracy correlate, with exceptions | "out-of-distribution performance is strongly correlated with in-distribution performance" | confirmed |
| S10 | https://arxiv.org/abs/2206.13089 | Agreement-on-the-Line (Baek, Jiang, Raghunathan, Kolter), NeurIPS 2022 | 2022-06 | Label-free OOD accuracy prediction | "without any labeled data, we can predict the OOD accuracy of classifiers" | confirmed |
| S11 | https://arxiv.org/abs/2201.04234 | Leveraging Unlabeled Data to Predict Out-of-Distribution Performance (Garg et al.), ICLR 2022 | 2022-01 | ATC and its impossibility limit | "the efficacy of any method rests upon (perhaps unstated) assumptions on the nature of the shift" | confirmed |
| S12 | https://arxiv.org/abs/1712.00377 | Don't Just Assume; Look and Answer (Agrawal et al.), CVPR 2018 | 2017-12 | Changed priors break VQA models | "for every question type, train and test sets have different prior distributions of answers" ... "their performance degrades significantly" | confirmed |
| S13 | https://arxiv.org/abs/2403.20330 | Are We on the Right Way for Evaluating Large Vision-Language Models? (Chen et al.) | 2024-03 | Blind baselines score high | "GeminiPro achieves 42.9% on the MMMU benchmark without any visual input" | confirmed |
| S14 | https://arxiv.org/abs/2204.13631 | Reliable Visual Question Answering: Abstain Rather Than Answer Incorrectly (Whitehead et al.), ECCV 2022 | 2022-04 | Effective reliability; low coverage at 1% risk | "an Effective Reliability metric for VQA that places a larger cost on incorrect answers compared to abstentions"; HTML Sec. 5.3: "we report Φ_c with cost values of 1, 10, and 100" | confirmed |
| S15 | https://arxiv.org/abs/2407.01032 | Overcoming Common Flaws in the Evaluation of Selective Classification Systems (Traub et al.) | 2024-07 | AUGRC | "can be directly interpreted as the average risk of undetected failures" | confirmed |
| S16 | https://arxiv.org/abs/2509.04664 | Why Language Models Hallucinate (Kalai, Nachum, Vempala, Zhang) | 2025-09 | Grading rewards guessing; confidence targets | "the training and evaluation procedures reward guessing over acknowledging uncertainty"; Sec. 4.2: "Answer only if you are >t confident, since mistakes are penalized t/(1−t) points" | confirmed |
| S17 | https://arxiv.org/abs/2506.09038 | AbstentionBench (Kirichenko, Ibrahim, Chaudhuri, Bell) | 2025-06 | Reasoning tuning hurts abstention | "reasoning fine-tuning degrades abstention (by $24\%$ on average)" | confirmed |
| S18 | https://arxiv.org/abs/2107.07511 | A Gentle Introduction to Conformal Prediction (Angelopoulos, Bates) | 2021-07 | Distribution-free intervals | "they possess explicit, non-asymptotic guarantees even without distributional assumptions or model assumptions" | confirmed |
| S19 | https://arxiv.org/abs/2411.00640 | Adding Error Bars to Evals (Evan Miller, Anthropic) | 2024-11 | Clustered SE, paired differences, MDE | "Analyzing the same data, clustered standard errors can be over 3X larger than naive standard errors."; "paired differences represent a “free” reduction in estimator variance when comparing two models." | confirmed |
| S20 | https://arxiv.org/abs/2010.06595 | With Little Power Comes Great Responsibility (Card et al.), EMNLP 2020 | 2020-10 | Underpowered comparisons common | "underpowered experiments are common in the NLP literature" | confirmed |
| S21 | https://aclanthology.org/P18-1128/ | The Hitchhiker's Guide to Testing Statistical Significance in NLP (Dror et al.), ACL 2018 | 2018-07 | Testing often misused | "statistical significance testing is often ignored or misused" | confirmed |
| S22 | https://direct.mit.edu/neco/article/10/7/1895/6224/Approximate-Statistical-Tests-for-Comparing | Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms (Dietterich), Neural Computation | 1998 | McNemar for one test set | Crossref record and abstract: "McNemar's test, is shown to have low type I error" (publisher page returned HTTP 403) | confirmed (via Crossref DOI record: title, author, journal, 1998; abstract says McNemar has low type I error). Publisher page itself still 403 |
| S23 | https://arxiv.org/abs/2406.12624 | Judging the Judges (Thakur et al.), GEM 2025 | 2024-06, rev. 2025-08 | Judge alignment, leniency, percent agreement misleads | "judges with high percent agreement can still assign vastly different scores" | confirmed |
| S24 | https://arxiv.org/abs/2503.05061 | No Free Labels: Limitations of LLM-as-a-Judge Without Human Grounding (Krumdick et al.) | 2025-03 | Reference answers needed | "providing the judges with expert-written references largely mitigates this issue" | confirmed |
| S25 | https://arxiv.org/abs/2606.19544 | Reliability without Validity (Norman, Rivera, Hughes) | 2026-06, withdrawn 2026-11 | Negative: withdrawn source, do not use | arXiv admin note: "does not meet arXiv's research content quality standards" | confirmed (arXiv page: withdrawn by arXiv Admin, v2 2026-11-03) |
| S26 | https://arxiv.org/abs/2103.14749 | Pervasive Label Errors in Test Sets Destabilize ML Benchmarks (Northcutt, Athalye, Mueller), NeurIPS 2021 | 2021-03 | Test-set label noise changes rankings | "we estimate an average of at least 3.3% errors across the 10 datasets" | confirmed |
| S27 | https://arxiv.org/abs/2502.03461 | Do Large Language Model Benchmarks Test Reliability? (Vendrow et al.) | 2025-02 | Label errors hide failures | "pervasive label errors can compromise these evaluations, obscuring lingering model failures" | confirmed |
| S28 | https://arxiv.org/abs/2406.04127 | Are We Done with MMLU? (Gema et al.) | 2024-06, rev. 2025-01 | Benchmark error rate | "We estimate that 6.49% of MMLU questions contain errors." | confirmed |
| S29 | https://github.com/cleanlab/cleanlab | cleanlab | opened 2026-11-13 | Licence Apache-2.0 | Repository licence shown as "Apache-2.0" | confirmed |
| S30 | https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ | Defeating Nondeterminism in LLM Inference (Horace He, Thinking Machines) | 2025-09-10 | Temperature 0 not deterministic | "Surprisingly, we generate _80_ unique completions, with the most common of these occuring 78 times." | confirmed |
| S31 | https://arxiv.org/abs/2408.04667 | Non-Determinism of "Deterministic" LLM Settings (Atil et al.) | 2024-08, rev. 2025-04 | Run-to-run accuracy spread | "We see accuracy variations up to 15% across naturally occurring runs." | confirmed |
| S32 | https://github.com/UKGovernmentBEIS/inspect_ai ; https://pypi.org/project/inspect-ai/ | Inspect AI | 0.3.289, 2026-11-10 | MIT licence, current release | "Inspect: A framework for large language model evaluations"; PyPI: "Released: Nov 10, 2026" | confirmed |
| S33 | https://inspect.aisi.org.uk/caching.html | Inspect caching docs | opened 2026-11-13 | Cache key design and expiry | "If all of these inputs are identical, then the model response will be served from the cache."; "By default, if you specify `cache = True` then the cache will expire in 1 week." | confirmed |
| S34 | https://github.com/promptfoo/promptfoo ; https://www.promptfoo.dev/blog/promptfoo-joining-openai/ | promptfoo | blog 2026-03-09 | MIT; acquisition | "Promptfoo has agreed to be acquired by OpenAI. Promptfoo will remain open source" (blog); MIT on GitHub repository page | corrected: the blog says "Promptfoo has agreed to be acquired by OpenAI. Promptfoo will remain open source" (2026-03-09). The quoted sentence is not on the page. MIT is confirmed on the GitHub repository |
| S35 | https://github.com/openai/evals | OpenAI evals | opened 2026-11-13 | Points to dashboard; no custom code | "You can now configure and run Evals directly in the OpenAI Dashboard."; "Please note that we are currently not accepting evals with custom code!" | confirmed |
| S36 | https://github.com/braintrustdata/autoevals | Braintrust autoevals | opened 2026-11-13 | MIT; numeric scorer | README lists "Numeric difference" under heuristic evaluations | confirmed |
| S37 | https://www.langchain.com/pricing | LangSmith pricing | opened 2026-11-13 | Free plan limits | "Up to 5k base traces / mo, then pay-as-you-go"; "Maximum of 1 seat (free)" | confirmed |
| S38 | https://platform.claude.com/docs/en/about-claude/pricing | Anthropic pricing | opened 2026-11-13 | Prices and Batch discount | "The Batch API allows asynchronous processing of large volumes of requests with a 50 percent discount on both input and output tokens."; table row "Claude Sonnet 5.5 \| $2 / MTok ... \| $10 / MTok" | confirmed (Opus 5.5 $4/$20, cache read $0.20; Sonnet 5.5 $2/$10, cache read $0.10; Batch 50 percent) |
| S39 | https://arxiv.org/abs/2005.04118 | Beyond Accuracy: Behavioral Testing of NLP Models with CheckList (Ribeiro et al.), ACL 2020 | 2020-05 | Behavioural tests find more bugs | "created twice as many tests, and found almost three times as many bugs" | confirmed |
| S40 | https://arxiv.org/abs/1708.08559 | DeepTest (Tian, Pei, Jana, Ray) | 2017-08 | Realistic transforms find errors | "DeepTest found thousands of erroneous behaviors under different realistic driving conditions" | confirmed |
| S41 | https://arxiv.org/abs/2512.15033 | Beyond Accuracy: A Geometric Stability Analysis of LLMs in Chess Evaluation (Hu et al.) | 2025-12, rev. 2026-11 | Frontier LLMs fail rotation invariance | "at most 10.6% of the 500 rotated pairs received evaluations within 300 centipawns (cp) of each other"; "means over answered pairs concealed most rotation failures" | confirmed |
| S42 | https://arxiv.org/abs/2605.19307 | MetaRA: Metamorphic Robustness Assessment for MLLM-based VQA (Xu et al.) | 2026-05 | Metamorphic tests expose VQA failures | "over-reliance on superficial visual cues" | confirmed |
| S43 | https://github.com/HypothesisWorks/hypothesis | Hypothesis | opened 2026-11-13 | Property-based testing in Python (licence MPL-2.0 per PyPI) | "The property-based testing library for Python" | confirmed; licence MPL-2.0 per PyPI (the GitHub page does not show it in text) |
| S44 | https://arxiv.org/abs/1608.00507 | Top-down Neural Attention by Excitation Backprop (Zhang et al.), ECCV 2016 | 2016-08 | Pointing game definition | "A hit is counted if the maximum point lies on one of the annotated instances of the cued object category, otherwise a miss is counted." (PDF Sec. 4.1) | confirmed |
| S45 | https://arxiv.org/abs/2605.12882 | CiteVQA: Benchmarking Evidence Attribution for Trustworthy Document Intelligence (Ma et al.) | 2026-05, rev. 2026-10 | Joint answer and evidence scoring; right answer, wrong region | "models frequently produce the right answer while citing the wrong region"; best "achieves an SAA of only 76.0" | confirmed |
| S46 | https://arxiv.org/abs/2304.09848 | Evaluating Verifiability in Generative Search Engines (Liu, Zhang, Liang), Findings of EMNLP 2023 | 2023-04 | Citation recall and precision | "on average, a mere 51.5% of generated sentences are fully supported by citations" | confirmed |
| S47 | https://arxiv.org/abs/2305.07722 | In Search of Verifiability (Fok, Weld) | 2023-05 | Explanations help only by enabling verification | "most tasks fundamentally do not allow easy verification, regardless of explanation method" | confirmed |
| S48 | https://arxiv.org/abs/2212.06823 | Explanations Can Reduce Overreliance on AI Systems During Decision-Making (Vasconcelos et al.), CSCW 2023 | 2022-12 | Verification cost drives reliance | "the explanation not sufficiently reducing the costs of verifying the AI's prediction" | confirmed |
| S49 | https://arxiv.org/abs/2502.08554 | Fostering Appropriate Reliance on LLMs (Kim et al.), CHI 2025 | 2025-02 | Explanations raise reliance; sources reduce reliance on wrong answers | "We find that the presence of explanations increases reliance on both correct and incorrect responses." | confirmed |
| S50 | https://arxiv.org/abs/2407.06581 | Vision Language Models Are Blind (Rahmanzadehgervi et al.) | 2024-07, rev. 2025-03 | VLMs weak at precise low-level vision | "four state-of-the-art VLMs are only 58.07% accurate on average" | confirmed |


## Verification

Date: 2026-11-13. Checked by an independent fact checker (a second pass over the research agent's report).

- Sources opened: 50 of 50 (S1-S50). 37 arXiv papers were read through abs pages (and PDFs for body quotes). S2, S21 and S22 were read on the NeurIPS, ACL and publisher sites. S29-S30, S32-S38 and S43 were opened as GitHub, docs, blog or pricing pages. Licences of Hypothesis, pytest, Pillow, OpenCV, PyMuPDF and numpy were read from PyPI.
- Result: 49 confirmed, 1 corrected, 0 partly, 0 not found. No finding needed an "UNVERIFIED" mark.
- Body quotes checked in PDFs: S2 (shift "more pressing", 120 Kaggle competitions), S3 (ladder and paired t-test), S11, S14 (Phi_c with c = 1, 10, 100; threshold chosen on validation), S16 (t/(1-t) in Sec. 4.2), S19 (3X, "free" reduction, 1,000 questions, MDE formula), S44.

Corrections:

1. S34: the quote "Promptfoo is now part of OpenAI. Promptfoo remains open source and MIT licensed." is not on the blog page. The page says "Promptfoo has agreed to be acquired by OpenAI. Promptfoo will remain open source" (2026-03-09). The MIT licence is true (GitHub repository). The claim in section 9 is unchanged.
2. Section 1 "What this means for us": the text said S2 shows an effect "under 1 point" and that S1 and S2 show a shift effect of "often 10 points or more". S2 gives about 1% for top submissions and no size for shift. S1 gives 3-15% and 11-14%. The text now says this.
3. S22: the "unverified" mark is removed. Crossref confirms title, author, journal and year, and the abstract says McNemar's test has low type I error. The publisher page still returns 403.
4. S43 Hypothesis licence added: MPL-2.0. pytest is MIT (was "not opened").
5. Pillow licence: PyPI lists "MIT-CMU" (the licence formerly called HPND). PyMuPDF is AGPL-3.0 or a paid Artifex licence.

Not checked here: the MEASURED numbers (computed on the local dataset) and the "Check of the prior research" table (local files). Those need a separate check. The "Fable" usage limit stopped the WebFetch tool, so all pages were read with curl.
