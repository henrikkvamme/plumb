# stoa

The new start on the Stoa challenge "Make Blueprints Talk". It replaces `stoa-drawings/`.

State on 14 November 2026: the research, the evaluation design and the decision are done. No solver and no
product UI exist yet.

## Read in this order

1. `docs/DECISION.md`: the recommended direction, the alternatives, what to build first, the risks. 10 minutes.
2. `video/out/make-blueprints-talk.mp4`: the explainer video, 4 minutes 35 seconds. See "The video" below.
3. `docs/QUESTIONS-FOR-STOA.md`: 15 ranked questions to take to the Stoa stand.
4. `docs/EVALUATION.md`: the evaluation environment. Build it before any solver.

## All documents

| File | Content |
|---|---|
| `docs/BRIEF.md` | The problem, the data, the judging and what to deliver |
| `docs/HOST.md` | What the Stoa host told us, with quotes, and what it changes |
| `docs/DATASET.md` | What the dataset holds, how the answers were made, and how a public score misleads |
| `docs/EVALUATION.md` | The decided evaluation design: contract, suites, scoring, statistics, build order |
| `docs/STATE-OF-THE-ART.md` | 11 topics, each source checked, with the claims that failed the check |
| `docs/SOLUTIONS.md` | 7 solution families compared; reinforcement learning, a Rust core and synthetic data weighed |
| `docs/PRIOR-RESEARCH.md` | The earlier research in `docs/inputs/prior-research/`, checked claim by claim |
| `docs/DECISION.md` | The decision |
| `docs/QUESTIONS-FOR-STOA.md` | Open questions for the host |
| `docs/research/data/` | 5 measured reports on the dataset, and 50 hand-made probe questions on the unlabelled sources |
| `docs/research/sota/` | 11 state-of-the-art reports, each with a source table and a verification section |
| `docs/research/ideas/` | 7 independent solution designs, one per lens |
| `docs/research/eval/` | 3 independent designs of the evaluation environment |
| `docs/inputs/` | The challenge brief, a photo of Stoa's platform, and the earlier research |
| `analysis/` | The scripts behind each measured number. Their outputs go to `analysis/**/out/` (git ignores it) |
| `data/` | The Stoa dataset (git ignores it). Download it from the links in `docs/inputs/challenge-brief.md` |

Each figure in the documents has a status: measured (a script in `analysis/` printed it), sourced (a paper or
the host said it) or estimate. An estimate is not a result.

## The video

- File: `video/out/make-blueprints-talk.mp4` (4 min 35 s, 1920x1080, 30 fps, 27 MB, narration with burned-in
  captions, no music). Poster: `video/out/poster.png`. Captions as a file: `video/out/make-blueprints-talk.srt`.
- Not checked yet: nobody has listened to the voice or watched the video in motion. The checks were stills,
  speech recognition and loudness measurement. `video/BUILD-NOTES.md` lists the known defects.
- Script: `video/SCRIPT.md`. It is the contract: the narration, the scenes, and a table of each number on screen with its source.
- How it was made, and how to render it again: `video/BUILD-NOTES.md`.
- Tools: HyperFrames (HTML scenes rendered to video from code, Apache-2.0), GSAP for motion, the Kokoro-82M voice
  (local, Apache-2.0), ffmpeg. Fonts: Inter and JetBrains Mono (SIL Open Font License). The research behind this
  choice is in `docs/research/sota/explainer-video-craft.md`.
- We did not use Toolcraft here, and this is a deliberate deviation from the repository rule for visual work.
  Toolcraft is for one visual that a person tunes by eye. This video is 10 scripted scenes that are cut to a
  narration track, with timed overlays on real drawings. A code-first video tool renders that from the script,
  and an agent can check each scene as a still.
- Drawings in the video, with the credit that the video shows:
  - a floor plan from CubiCasa5K, (c) 2019 CubiCasa, CC BY-NC-SA 4.0 (non-commercial);
  - a sheet from Swiss Dwellings v3.0.0, Archilyse AG, CC BY 4.0, as drawn by Stoa;
  - a historic drawing from Helsingin kaupunginarkisto, CC BY 4.0, through Finna.
- The video is for the team and the pitch. Because of the CubiCasa5K plan, do not use it commercially.

## Licences to remember

- The dataset stays out of the repository. `docs/DATASET.md` section 7 has the licence of each source.
- CubiCasa5K is non-commercial. A model that is trained on it is for the hackathon only, unless Stoa has a licence.
- PyMuPDF and Ultralytics are AGPL-3.0. They are fine for the weekend. pypdfium2 and RF-DETR are the permissive choices.
