# Stoa: the problem

This is the brief for the Stoa challenge "Make Blueprints Talk" at Junction 2026. It states the problem, the
facts and the constraints. It does not give a solution. Finding the solution is the work.

`stoa/` replaces `stoa-drawings/`. We do not keep any code from `stoa-drawings/`. Read it only as a record of
what one earlier attempt tried.

## The task

Build a program that answers natural-language questions about construction drawings and building models.
The answers must be correct, and a person must be able to check each answer in seconds. The full brief is in
`inputs/challenge-brief.md`.

Stoa wants approaches that next year's frontier models will not make obsolete. Their examples are hybrids of
frontier models, computer vision, 3D, geometry and small fine-tuned models.

## How we are judged

Four criteria, 25% each:

1. Accuracy of answers.
2. How well the solution shows its reasoning, so a person can check the answer.
3. Creativity.
4. Low inference cost.

Prizes: €1,000 and a work trial at Stoa, €750, €250.

**Most important: the score on Stoa's hidden test set.** We do not know its contents. We assume it is like the
public question set, but it can contain other drawings, other templates, other languages and other sources.
A solution that is tuned only to the public questions can fail on it.

## The data

The dataset is local and git ignores it (Stoa's licence terms). It also downloads from the links in the
challenge brief.

- `stoa/data/junction-dataset/`: the full set, 11 GB, about 15,000 files, 127,044 questions on 5,939 drawings.
- `stoa/data/junction-dataset-preview/`: the 0.5 GB preview, 7,990 questions on 320 drawings.
- Read the dataset `README.md` and the `LICENSE.md` in each source folder.

Measured facts about the full question set:

- Each row is `{path, question, answer, unit, type}`. Each question names exactly one file.
- Types: count 111,763; area 14,243; text 836; volume 138; length 64.
- Scoring per the dataset README: counts must be exact. Areas, lengths and volumes must be within 2%.
  Text answers are free-form, and no scoring rule is published for them.
- Sources with questions: `cubicasa5k` (85,514, all counts, PNG floor plans), `swiss_dwellings` (25,568 counts
  and 12,016 areas, PDF with DXF and PNG copies), `ifc_models` (IFC models and plans rendered from them),
  `ifc_bench` (820 free-text questions on IFC models), `opening_design` (64 questions on a US practice's drawing sets).
- Sources with no questions: `habs`, `finna`, `europeana` and `wikimedia`, about 6,700 historic scans.
- Files with the same name and another extension are the same drawing in another format.
- Questions come from templates, often as pairs: English plus the drawing's local language.
- Some questions on a rendered plan PDF ask about the whole model, so the answer is not on that sheet.

Check these facts yourself. Do not trust any figure in `inputs/prior-research/` that you have not measured.

## Constraints

- Time: the final submission is Sun 15 November, 10:00 (Helsinki). Peer review and pitches follow.
- Compute: Verda GPUs through `pnpm j gpu` (read `infra/verda/README.md`). Verda sponsors our track, so a model
  trained on Verda is a plus. Ask Henrik before you start anything above $10/h. Delete VMs when you are done.
- Claude API models are available. Each API call counts against the inference-cost criterion.
- Public data and models with licences that allow non-commercial hackathon use are fine. Record each licence.
- Leakage: some public datasets overlap with Stoa's drawings. A score that relies on leaked labels does not
  transfer to the hidden test set, and judges will ask about it.

## Context from Stoa

- `inputs/stoa-platform-photo.jpg` is a photo of Stoa's own product at their stand. It shows stacked 3D floor
  plans, a construction schedule (Gantt) with issue markers, and an AI panel that explains an issue with
  citations. It shows what they build and how they show evidence today.
- Read every conversation in `context/stoa-drawings/` before you decide anything. No host talk was recorded
  when this brief was written. Check again, because the team records new talks during the event.
- Open questions for Stoa are in `inputs/prior-research/weekend-plan.md`, section 6.

## What Henrik asks for, in order

1. **An evaluation environment we can trust.** This matters most. It must tell us whether a change makes the
   hidden-test score better or worse. Think about held-out splits that look like a hidden test set,
   per-source and per-template reports, cost per question, abstentions, regressions, and runs that we can
   reproduce. A good first goal is to score well on the public set. Then use that work as building blocks for
   the hidden set.
2. **Deep research on the state of the art** in this domain: recent papers, benchmarks, models and tools.
   Verify each source.
3. **Many different solution ideas.** Compare them on the four criteria and on how well they generalize to
   the hidden test set. Discuss more than one design.
4. **A recommended direction** with the reasons, the risks and what to measure first.
5. **An explainer video** of the problem, the solution space and what to consider. It must be beautiful and
   clear. Research how the best technical explainer videos are made, and the tools for them, before you make it.

The product UI comes later. Do not build it now.

## Henrik's leanings (discuss them, do not assume them)

- Reinforcement learning can be a good fit, because many answers can be checked automatically.
- A Rust core and a Rust test framework can be less error-prone. Python can be the language for training.
- A synthetic dataset can help with training and with evaluation.
- Many sources and many formats exist. One method may not fit all of them.

## Where to put results

- Research, comparisons and decisions: `stoa/docs/`.
- The video and its source: in `stoa/`, in a place you choose. Record the choice in `stoa/README.md`.
- Log progress in the hq CRM (slug `stoa-drawings`), as the root `AGENTS.md` says.
