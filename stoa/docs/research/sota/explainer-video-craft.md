# Explainer video: craft, tools and a pipeline for the Stoa video

Research track: how the best technical explainer videos are made, and which tools let a coding agent make a
2 to 4 minute explainer of "Make Blueprints Talk" in a few hours on a headless Mac.

Date: 2026-11-13. Author: research subagent for the Stoa lead.

## Method and limits of this pass

- The `WebSearch` and `WebFetch` tools hit a usage limit at the start of this pass. I could not run web searches.
- I fetched primary pages directly with `curl` (docs, READMEs, model cards, arXiv abstracts, GitHub and npm and
  PyPI metadata), and read the text. Each quote in the Sources table comes from a page I opened in this pass.
- Because I could not search, I found no primary text from Kurzgesagt, Vox, Welch Labs, Primer, Fireship,
  Josh Starmer, Reducible, Linear, Stripe or Apple on how they make videos. Their pages that I tried were
  empty shells or failed. Claims about those creators below are marked UNVERIFIED (from memory).
- Labels: **[M]** = measured on this machine or read from a registry API. **[S]** = read in a source in this pass.
  **[E]** = my estimate. **[U]** = unverified, from memory.

## Findings that change decisions

1. **Script and voice first, then visuals, one purpose per movement.** Grant Sanderson (3Blue1Brown) says every
   movement must be deliberate and must say the same thing as the narration. He also says he worries when people ask how to
   sync narration inside the animation tool; it is a tool for clips that are edited together later [S1]. For us: write and voice the script
   first, then cut each scene to the length of its audio. [S] Moves criterion: clarity of the pitch (not a judging
   criterion itself, but it sells "verifiability" and "creativity").
2. **Pick an HTML-to-video framework with agent skills, not Manim and not an AI video model.** HyperFrames
   (HeyGen, Apache-2.0, v0.9.42, updated today) and Remotion (v4.0.543, own licence) both render web pages frame by
   frame to MP4 and ship official Claude Code skills [S2][S3][S4]. [M] Both can show a real PNG floor plan, an SVG
   from a PDF or DXF, and animated SVG overlays, zooms and counters, because the frame is a browser page. [E]
3. **Licences are clear for us.** Remotion is free for "an individual" and for a for-profit company "with up to
   3 employees" [S5]; a hackathon team of individuals fits. [E] HyperFrames is Apache-2.0 [S2][M]. GSAP, which
   HyperFrames uses for timing, is now free "even for commercial use" [S6]. Remotion Creator seats cost $25 per
   month per person if a company licence is ever needed [S7].
4. **AI pixel video models do not fit a precise technical diagram video.** Code2Video (Oct 2025) states that
   pixel-space generators "remain limited in producing professional educational videos, which demand disciplinary
   knowledge, precise visual structures, and coherent transitions" [S8]. A real floor plan with exact counts must be
   drawn from code. Use generated video at most for a 3 second mood shot. [S] I could not open the Sora, Kling or
   Runway pages, so their current failure modes are [U]: wrong text, wrong counts, unstable geometry between frames.
5. **The known agent failure is layout, so the review loop must look at frames.** TheoremExplainAgent (ACL 2025):
   agent-made Manim videos succeed 93.8% of the time, but "most of the videos produced exhibit minor issues with
   visual element layout" [S9]. Code2Video adds a VLM "Critic" with "visual anchor prompts" to fix layout [S8].
   For us: render a still per scene, look at each still, fix, and only then render the full video. [S]
6. **Local voice is good enough and free; one retired option to avoid.** Kokoro-82M is Apache-2.0, 82 million
   parameters, and runs locally [S10]; HyperFrames uses Kokoro as its free local voice [S11]. Chatterbox is
   "retired research and is no longer maintained" since August 2026 [S12]. Dia is English only [S13]. ElevenLabs v4
   costs $0.08 per 1,000 characters [S14], so a 3 minute script (about 2,700 characters [E]) costs about $0.22 [E].
   macOS `say` has 187 voices here and none marked Premium or Enhanced [M]: do not use it.
7. **Pace: about 150 words per minute, so 3 minutes is about 450 words.** Audiobooks are recommended at 150 to 160
   wpm; slide presentations are closer to 100 to 125 wpm [S15]. A dense diagram video should sit near 140 to 150
   wpm [E], so plan 420 to 450 words for 3 minutes [E]. Captions: about 0.3 s per word minimum on screen [S16]. The 37-character line limit in the BBC guide is for broadcast Teletext only.
8. **The repo names Toolcraft for "a video for the pitch".** `AGENTS.md` says to use Toolcraft for "branded
   assets or a video for the pitch", and warns that a first result "takes well over an hour". [S, repo] This is a
   process decision for the lead: Toolcraft for tuned visual pieces, or a framework above for the narrated
   explainer. I did not research Toolcraft's video export in this pass.

## Landscape

### Craft: what the best explainers do

| Principle | Evidence | Status |
| --- | --- | --- |
| Every movement has a purpose and matches the narration | 3Blue1Brown FAQ [S1] | [S] |
| Do not start with definitions; pedagogical order differs from logical order | 3Blue1Brown FAQ [S1] | [S] |
| Always ask what picture explains the idea; it need not be fancy | 3Blue1Brown FAQ [S1] | [S] |
| Animation tool makes clips; edit with narration in a video editor | 3Blue1Brown FAQ [S1] | [S] |
| Interesting content beats production value | SoME1 results: lower production quality but highly interesting lessons rose to the top [S17] | [S] |
| One idea, one visual stage, reveal the mechanism one layer at a time | HyperFrames explainer guide ("open with a useful question, then reveal the mechanism one layer at a time") [S18] | [S], vendor doc |
| Name the misconception, then resolve it | Derek Muller's PhD thesis "Designing Effective Multimedia for Physics Education" [S19]; the misconception finding itself is [U] | partial |
| Slow in and slow out, staging, timing (Disney principles) | Wikipedia list of the twelve principles [S20] | [S], secondary |
| Hook in the first 5 to 10 seconds with a concrete question | Common practice of Veritasium, Vox, Fireship | [U] |
| Persistent object continuity: transform the same object across scenes instead of cutting (3Blue1Brown `Transform`, Apple keynote product continuity) | Manim CE has `Transform` animations [S21]; the keynote claim is [U] | partial |
| Strict colour system: few colours, each with one meaning (Kurzgesagt, Primer, Welch Labs) | [U] | [U] |
| Sound: music bed ducked under voice, sparse effects on scene changes | HyperFrames audio guide [S11] | [S], vendor doc |

### Tools (versions measured from npm, PyPI and the GitHub API on 2026-11-13)

| Tool | Version, date | Licence | Agent support | Real drawings with overlays | Verdict for us |
| --- | --- | --- | --- | --- | --- |
| HyperFrames (HeyGen) | 0.9.42, npm modified 2026-11-13; 83,911 stars [M] | Apache-2.0 [M][S2] | Official Claude Code plugin and 9 skills; lint, preview, render [S2] | Yes: HTML, SVG, images, GSAP [S3] | Primary candidate. Pre-1.0 and changes daily [M]: pin the version. |
| Remotion | 4.0.543, 2026-11-11; 72,993 stars [M] | Own licence; free for individuals and companies up to 3 employees [S5] | `npx remotion skills add`, 13 skills [S4] | Yes: React, SVG, images; `@remotion/layout-utils` has `fitText`, `measureText` [S22] | Strong fallback. Mature. About 950 MB `node_modules` in the vendor's test [S3]. |
| Manim Community | 0.22.1, 2026-10-27 [M] | MIT [M] (GitHub) | `manim_skill` (best practices for CE and ManimGL) [S23]; `manim-mcp-server` [S24] | Images yes; web typography and SVG overlays weaker [E]; needs LaTeX for formulas [U] | Use only for one formula scene, if any. Not installed [M]. |
| ManimGL | 1.7.2 [M] | MIT [M] | Same skill [S23] | As above | No: Grant calls it a testing ground [S1]. |
| manim-voiceover | plugin | [U] | Per-word timing of animations [S25] | n/a | Only if Manim is chosen. |
| Motion Canvas | 3.17.2, last release 2024-12-14; repo push 2026-07-02 [M] | MIT [M] | None found | Yes (canvas 2D) | No: no release in 23 months [M]. |
| Revideo | 0.11.0, 2026-07-10 [M] | MIT [M] | README says Claude or Codex can write a scene [S26] | Yes | No: smaller ecosystem, no skills [E]. |
| Theatre.js | 0.7.2, 2024-05; repo push 2024-08 [M] | Apache-2.0 [M] | None | Yes | No: stale [M]. |
| GSAP | 3.15.1 [M] | Free standard licence, commercial use allowed [S6] | Used inside HyperFrames | Yes | Use through HyperFrames. |
| Rive, Cavalry, After Effects | Rive and Cavalry are free to start [S27][S28] | Proprietary | GUI tools, no headless agent path [E] | Yes | No for an agent on a headless Mac. |
| Blender Grease Pencil | Blender.app is installed [M] | GPL [U] | Python scripting possible [U] | Possible | No: too slow to set up this weekend [E]. |
| Veo 3.1, Sora 2, Kling, Runway | Veo 3.1 is Google's current model with native audio [S29] | Paid APIs | Prompt only | No exact geometry or counts [S8] | No, except a short mood shot. |

### Voice and timing

| Option | Licence, price | Local on Apple Silicon | Notes |
| --- | --- | --- | --- |
| Kokoro-82M | Apache-2.0 [S10] | Yes: Python `kokoro`, `kokoro-js` (ONNX) [S30], MLX ports in `mlx-audio` [S31] | Free. English quality is good [U]. Needs espeak for fallback words [S32]. |
| ElevenLabs v4 | $0.08 per 1K chars; v4 Turbo $0.04 [S14] | No | Best naturalness by reputation [U]. About $0.22 for our script [E]. |
| Gemini 3.8 Flash TTS | price not checked | No | Over 130 languages, style in `speech_metadata.style`, inline tags such as `<short pause>` [S33]. |
| OpenAI `gpt-4o-mini-tts` | price not checked | No | Accepts `instructions` for tone [S34]. |
| Cartesia Sonic | Free tier 20K credits per month [S35] | No | Low latency focus. |
| Chatterbox | MIT, archived | Yes | Retired August 2026 [S12]. Avoid. |
| Dia 1.6B | Apache-2.0 [S13] | Possible | English only [S13]. |
| macOS `say` | built in | Yes | 187 voices, 0 Premium or Enhanced listed [M]. Robotic [U]. |

Timing and captions:

- whisper.cpp runs on Apple Silicon "fully on the GPU via Metal" [S36]. Remotion wraps it in
  `@remotion/install-whisper-cpp` with `transcribe()` and `toCaptions()` [S37].
- WhisperX gives "word-level timestamps" [S38]. `mlx-audio` lists `Qwen3-ForcedAligner` for word-level alignment [S31].
- HyperFrames transcribes locally: `npx hyperframes transcribe <file>` [S11].
- Simplest robust method [E]: one TTS clip per scene; read each clip length with `ffprobe`; set the scene length to
  clip length plus 0.4 s. Use word timestamps only for a few "hit points" (a count appears when the word is said).
  This removes drift across the whole video by design.
- Loudness: Spotify normalises to -14 LUFS (ITU 1770) [S39]. I use -14 LUFS integrated, -1 dBTP true peak as the
  target for web playback [E]. YouTube's exact target is [U]. EBU R128 (-23 LUFS) is for broadcast [U, PDF not parsed].
- Music: YouTube Audio Library tracks under Creative Commons need credit in the description [S40]. Incompetech offers
  CC attribution or a paid standard licence [S41]. Free Music Archive tracks carry per-track licences [S42].
  Stable Audio Open uses the Stability AI Community Licence; commercial use needs a separate licence [S43].

## What we can use this weekend

Effort figures are estimates [E] for one agent plus the lead reviewing.

| Step | Tool and command | Licence | Effort |
| --- | --- | --- | --- |
| Script (420 to 450 words, 8 scenes) | Lead plus Claude, in a `script.md` with one block per scene | n/a | 1.0 h |
| Assets from real data | cubicasa5k PNG as is; swiss_dwellings PDF to SVG with `inkscape --export-type=svg` (installed [M]); DXF to SVG with `ezdxf` drawing add-on (MIT [S44]); ifc_models already has 107 SVGs [M] | dataset licence: check `LICENSE.md` per source | 1.0 h |
| Voice | Kokoro-82M locally, or ElevenLabs v4 for the final cut | Apache-2.0 / paid | 0.5 h |
| Scenes | HyperFrames with its skills; GSAP timelines; SVG overlays drawn with stroke animation | Apache-2.0 | 3.0 to 4.0 h |
| Review loop | Render one still per scene; check stills; fix; render full | n/a | 1.0 h |
| Mix and master | `ffmpeg` with `loudnorm` to -14 LUFS, music ducked about 12 dB under voice [E] | LGPL/GPL build | 0.5 h |
| Total | | | 7 to 8 h [E] |

Data facts that make the video concrete [M]: cubicasa5k has 4,787 PNG files; swiss_dwellings has 1,040 each of PDF,
DXF and PNG (the same drawing in three formats, a strong visual for "one question, three representations");
ifc_models has 533 IFC, 107 PDF, 500 PNG and 107 SVG files.

## What does not work

- **Pixel video generators for the core content.** No exact geometry, counts or legible labels [S8]. Their
  frame-to-frame instability is [U] but widely reported.
- **Syncing narration inside the animation tool by hand.** Grant Sanderson says he worries when people ask for it, and says to use video-editing software [S1].
  Drive scene length from audio length instead [E].
- **Trusting agent layout without looking.** Layout defects are the most common issue in agent-made explainer
  videos [S9].
- **Motion Canvas and Theatre.js this weekend.** No release since December 2024 and May 2024 [M].
- **Chatterbox.** Retired, no updates [S12].
- **Animation for decoration.** "Displaying a series of equations or text that are unnecessarily moving around" is
  the named failure [S1].

## Open questions

1. Toolcraft or HyperFrames or Remotion? `AGENTS.md` names Toolcraft for "a video for the pitch". The lead decides.
2. Does the Stoa submission require a video length or format? Not checked in this pass.
3. May frames from the dataset appear in a public video? Each source has its own `LICENSE.md`; the brief says the
   dataset is under Stoa's licence terms. Check before publishing.
4. ElevenLabs or Gemini TTS account and key: does the team have one? Kokoro needs none.
5. Does HyperFrames render headless on macOS 27 with Node 26? Its README asks for Node 22+ and FFmpeg [S2]; not tested.

## Recommended pipeline

**Primary: HyperFrames + Kokoro (local) + ffmpeg.** Reasons: Apache-2.0 with no licence question; plain HTML that
the lead can open in Brave; official Claude Code skills with lint, preview and render [S2]; Kokoro and local
transcription built in [S11]; no 950 MB install [S3]. Risk: pre-1.0, changes daily [M]. Pin the version.

**Fallback: Remotion** (same scene plan, React instead of HTML; free for us [S5]; `fitText` against overflow [S22];
whisper.cpp captions [S37]).

**Last resort (1.5 h [E]):** Python renders one PNG per beat (matplotlib over the real plan), Kokoro audio per
scene, and `ffmpeg` joins stills with crossfades and slow zooms (`zoompan`).

### Style guide

- Canvas: 1920x1080, 30 fps. Safe margin 96 px. 12-column grid.
- Background: near black `#0E1116` (dark, like a blueprint light table) with drawings shown on a light paper card
  `#F4F1EA`, so real scans keep their own contrast. [E]
- Palette with one meaning per colour (Okabe-Ito colour-blind safe set [S45]; hex values [U]):
  blue `#0072B2` = the question; orange `#E69F00` = evidence on the drawing (boxes, counted items);
  bluish green `#009E73` = verified answer; vermillion `#D55E00` = error or "I do not know"; grey `#8A93A3` = context.
- Fonts: Inter for text, JetBrains Mono for numbers, units and file names. Both OFL [U]. Two weights only (400, 600).
  Title 72 px, body 40 px, labels 28 px minimum. [E]
- Motion rules [E, following slow in and slow out [S20]]: entrances ease-out 0.4 to 0.6 s; moves and zooms
  ease-in-out 0.8 to 1.2 s; never linear except counters; one main motion at a time; stagger lists by 80 ms.
- Continuity: the same floor plan stays on screen across scenes 2 to 6 and zooms, rather than cutting away. [E]
- Scene length: 12 to 25 s, one idea each. Text on screen at most 7 words. Captions at most 2 lines. BBC's 37 characters is a broadcast Teletext limit; online it sets a width limit (68% of a 16:9 frame), so use about 37 to 42 characters as our own choice [E]. At least 0.3 s per word [S16].
- Sound: one calm music bed, ducked under voice; one soft whoosh per scene change; one tick per counted item. [E]
  Master to -14 LUFS [S39][E].

### Scene template (3 min, about 440 words [E])

| # | Time | Idea | Visual |
| --- | --- | --- | --- |
| 1 | 0:00-0:12 | Hook: "How many bathrooms are on this plan?" | Real cubicasa5k PNG fades in; question types on in blue. |
| 2 | 0:12-0:35 | The task: any question, any drawing, 30 languages | Same question in English and Finnish; PNG, PDF, DXF, IFC cards fan out (swiss_dwellings triple). |
| 3 | 0:35-0:55 | Why it is hard: scans, scale, hidden test set | Zoom to a historic scan; a scale bar is missing; vermillion "?" |
| 4 | 0:55-1:20 | How you are judged: four 25% bars | Four bars fill: accuracy, verifiability, creativity, cost. |
| 5 | 1:20-1:50 | Solution space | Three lanes: vector geometry (DXF, IFC), computer vision (raster), frontier model reasoning; router picks one. |
| 6 | 1:50-2:20 | Show the evidence | On the plan, orange boxes appear one by one with ticks; counter reaches the answer; green check. |
| 7 | 2:20-2:40 | Say "I do not know" | No scale: answer card turns vermillion and asks for a scale. |
| 8 | 2:40-3:00 | What to consider, close | Three short takeaways; final frame with team and repo name. |

### Setup commands (not run in this pass)

```sh
# installed [M]: ffmpeg 8.1.1, node v26.13.1, pnpm 11.21.0, uv 0.12.3, Python 3.13.13, inkscape, rsvg-convert, Blender
# missing [M]: manim, pdftocairo, mutool

# Primary
cd ./stoa
npx hyperframes@0.9.42 init video && cd video
npx hyperframes@0.9.42 skills update        # installs the core skills for Claude Code
npx hyperframes@0.9.42 preview              # live preview in the browser
npx hyperframes@0.9.42 render               # MP4

# Local voice (Python route)
brew install espeak-ng                      # fallback phonemes for Kokoro [S32]
uv venv .venv-tts && uv pip install --python .venv-tts "kokoro>=0.9.4" soundfile

# Fallback
npx create-video@latest --yes --blank video-remotion && cd video-remotion
npx remotion skills add
npx remotion still <CompositionId> --frame=120 out/check.png   # one still per scene for review [U flags]
npx remotion render

# Master
ffmpeg -i mix.wav -af loudnorm=I=-14:TP=-1:LRA=11 -ar 48000 master.wav
ffmpeg -i video.mp4 -i master.wav -c:v copy -c:a aac -b:a 192k -shortest final.mp4
```

### Review loop for the agent [S8][S9][E]

1. For each scene, render stills at 0%, 50% and 100% of its length.
2. Check: no text overflow or overlap; text is at least 28 px; overlays sit on the right drawing features; one colour
   per meaning; nothing moves without a reason.
3. Check audio: each scene's length equals its voice clip plus padding; hit points land on the spoken word.
4. Fix, render stills again, then render the full video once. Watch it end to end at 1x before export.

## Check of the prior research

- `weekend-plan.md` and `research-tracks.json` in `stoa/docs/inputs/prior-research/` contain no track on video,
  voice or motion tools. I found no claim on this topic to confirm or correct. [S, repo]
- The only related line is the schedule: Sunday 04-10, "Pitch, demo video, submit by 09:00". That agrees with the
  10:00 deadline and leaves one hour of margin. The video should be done on Saturday evening, not Sunday. [E]

## Sources

All pages fetched on 2026-11-13 with `curl` unless noted. "Date" is the page or release date when shown.

| id | URL | Title | Date | Claim it supports | Exact supporting quote | check |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | https://www.3blue1brown.com/faq | 3Blue1Brown FAQ (Grant Sanderson) | undated, read 2026-11-13 | Purposeful movement; clips edited later; no definitions first | "Every movement on the screen should be deliberate, with an identifiable purpose." / "This is just a tool for making individual clips to be edited together later." / "Never start with definitions." | partly: purposeful movement, clips edited later, "Never start with definitions", "testing ground" and the decorative-motion quote are confirmed. Grant writes "I worry when I hear people ask ... how do I sync up narration into manim?". He does not call it "the wrong question". |
| S2 | https://raw.githubusercontent.com/heygen-com/hyperframes/main/README.md | HyperFrames README (HeyGen) | main, 2026-11-13 | Apache, agent skills, CLI, requirements | "HyperFrames is a free, open-source framework for turning HTML, CSS, media, and seekable animations into deterministic MP4 videos." / "Requirements: Node.js 22+, FFmpeg" | confirmed |
| S3 | https://hyperframes.heygen.com/guides/hyperframes-vs-remotion.md | HyperFrames vs Remotion (HeyGen, vendor) | read 2026-11-13 | Both render web pages; install size; licence | "Both open a real browser, draw each frame, and encode the result." / "about 950 MB of `node_modules`" | confirmed (950 MB, Apache 2.0, Remotion free for individuals and up to three people) |
| S4 | https://www.remotion.dev/docs/ai/skills | Remotion Agent Skills | updated 2026-11-13 | Official skills for Claude Code | "In a Remotion project, install them by running: npx remotion skills add" | confirmed |
| S5 | https://raw.githubusercontent.com/remotion-dev/remotion/main/LICENSE.md | Remotion License | 2026 | Free licence eligibility | "a for-profit organization with up to 3 employees" | confirmed |
| S6 | https://gsap.com/blog/3-13/ | GSAP 3.13 blog (Webflow) | 2025 [U] | GSAP free for commercial use | "the entire GSAP toolset is FREE, even for commercial use!" | confirmed (blog post for GSAP 3.13; year not checked) |
| S7 | https://www.remotion.dev/docs/license/pricing | Remotion License and Pricing | updated 2026-11-13 | Seat price | "Remotion Creators" ... "$25/mo per seat" (surrounding words were dropped by the proxy) | confirmed ($25/mo per seat for "Remotion Creators") |
| S8 | https://arxiv.org/abs/2510.01174 | Code2Video (Chen, Lin, Shou) | 2025-10-01 | Pixel generators fail at precise educational video; VLM critic for layout | "While recent generative models advance pixel-space video synthesis, they remain limited in producing professional educational videos, which demand disciplinary knowledge, precise visual structures, and coherent transitions" | confirmed |
| S9 | https://arxiv.org/abs/2502.19400 | TheoremExplainAgent (Ku et al.), ACL 2025 | 2025-02-26, rev. 2025-05-25 | Agent videos have layout defects | "most of the videos produced exhibit minor issues with visual element layout" | confirmed |
| S10 | https://huggingface.co/hexgrad/Kokoro-82M | Kokoro-82M model card | read 2026-11-13 | Licence and size | "License: apache" / "With Apache-licensed weights, Kokoro can be deployed a[nywhere]" | confirmed |
| S11 | https://hyperframes.heygen.com/guides/voice-and-audio.md | HyperFrames: voiceover, music, sound effects and captions | read 2026-11-13 | Local Kokoro voice; local transcription; music ducking | "Kokoro voices, in several languages" / "npx hyperframes transcribe interview.mp4 --language es" | confirmed |
| S12 | https://raw.githubusercontent.com/resemble-ai/chatterbox/master/README.md | Chatterbox README (Resemble AI) | Aug 2026 notice | Chatterbox retired | "As of August 2026, Chatterbox is retired research and is no longer maintained." | confirmed |
| S13 | https://raw.githubusercontent.com/nari-labs/dia/main/README.md | Dia README (Nari Labs) | read 2026-11-13 | English only; Apache-2.0 | "The model only supports English generation at the moment." / "Apache License 2.0" | confirmed |
| S14 | https://elevenlabs.io/pricing/api | ElevenLabs API pricing | read 2026-11-13 | TTS price | "v4 Text to Speech New $0.08 Price per 1K characters" | confirmed |
| S15 | https://en.wikipedia.org/wiki/Words_per_minute | Words per minute (Wikipedia, secondary) | read 2026-11-13 | Narration pace | "Audiobooks are recommended to be 150–160 words per minute" / "Slide presentations tend to be closer to 100–125 wpm" | confirmed |
| S16 | https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/ | BBC Subtitle Guidelines | read 2026-11-13 | Caption timing and line length | "aim to leave a subtitle on screen for a minimum period of around 0.3 seconds per word" / "line length is limited to 37 fixed-width (monospaced) characters" | partly: 0.3 s per word confirmed. 37 characters is the broadcast Teletext limit. For online video BBC gives a width limit (68% of a 16:9 frame), not a character count. |
| S17 | https://www.3blue1brown.com/blog/some1-results | SoME1 results (3Blue1Brown) | 2021 [U] | Content beats production value | "lower production quality but highly interesting lessons still managed to bubble toward the top" | confirmed (year not checked) |
| S18 | https://hyperframes.heygen.com/guides/faceless-explainer.md | HyperFrames: explainer video guide (vendor) | read 2026-11-13 | One idea, layered reveal | "open with a useful question, then reveal the mechanism one layer at a time" | confirmed |
| S19 | https://en.wikipedia.org/wiki/Derek_Muller | Derek Muller (Wikipedia) | read 2026-11-13 | Muller's PhD topic | "completed in 2008 with the thesis, Designing Effective Multimedia for Physics Education" | confirmed |
| S20 | https://en.wikipedia.org/wiki/Twelve_basic_principles_of_animation | Twelve basic principles of animation (Wikipedia) | read 2026-11-13 | Easing and staging | Section headings "Staging" and "Slow in and slow out" | confirmed (headings; secondary source) |
| S21 | https://docs.manim.community/en/stable/changelog.html | Manim Community v0.22.1 docs | v0.22.1 | Version; Transform family exists | "Manim Community v0.22.1" (reference list includes "transform") | confirmed (v0.22.1 changelog; Transform not separately checked) |
| S22 | https://www.remotion.dev/docs/layout-utils/ | @remotion/layout-utils | read 2026-11-13 | Text fitting helpers | "measureText() fillTextBox() fitText() fitTextOnNLines()" | confirmed |
| S23 | https://raw.githubusercontent.com/adithya-s-k/manim_skill/main/README.md | Manim Skill (adithya-s-k) | read 2026-11-13 | Agent skill for Manim | "A comprehensive collection of best practices, patterns, and examples for both Manim Community Edition and ManimGL" | confirmed |
| S24 | https://raw.githubusercontent.com/abhiemj/manim-mcp-server/main/README.md | Manim MCP Server | read 2026-11-13 | MCP server for Manim | "This is an MCP (Model Context Protocol) server that executes Manim animation code and returns the generated video." | confirmed |
| S25 | https://raw.githubusercontent.com/ManimCommunity/manim-voiceover/main/README.md | Manim Voiceover README | read 2026-11-13 | Word-level sync in Manim | "Per-word timing of animations, i.e. trigger animations at specific words in the voiceover" | confirmed |
| S26 | https://raw.githubusercontent.com/redotvideo/revideo/main/README.md | Revideo README | 0.11.0, 2026-07 | Agent-writable scenes | "A scene is plain TypeScript, so Claude or Codex can produce one from a prompt." | confirmed |
| S27 | https://rive.app/pricing | Rive pricing | read 2026-11-13 | Free tier | "Build and ship for free" | confirmed |
| S28 | https://cavalry.scenegroup.co/pricing | Cavalry | read 2026-11-13 | Free | "Professional, real-time animation software. For free." | confirmed |
| S29 | https://deepmind.google/models/veo/ | Veo 3.1 (Google DeepMind) | read 2026-11-13 | Current Veo with audio | "Veo 3.1 Video, meet audio." | confirmed (page title "Veo 3.1", text "Video, meet audio.") |
| S30 | https://raw.githubusercontent.com/hexgrad/kokoro/main/kokoro.js/README.md | kokoro-js README | 1.2.1 | Node route for Kokoro | "npm i kokoro-js" / "onnx-community/Kokoro-82M-v1.0-ONNX" | confirmed |
| S31 | https://raw.githubusercontent.com/Blaizzy/mlx-audio/main/README.md | mlx-audio README | 0.6.5 [M] | MLX TTS and aligner on Apple Silicon | "Qwen3-ForcedAligner | Word-level audio alignment" | confirmed |
| S32 | https://raw.githubusercontent.com/hexgrad/kokoro/main/README.md | Kokoro README | read 2026-11-13 | espeak fallback | "used for English OOD fallback and some non-English languages" (said of espeak) | confirmed |
| S33 | https://ai.google.dev/gemini-api/docs/speech-generation | Gemini API speech generation | read 2026-11-13 | Languages and style control | "supports over 130 languages" / "Insert `<short pause>` or `<long pause>` at exact points" | confirmed (model is `gemini-3.8-flash-tts`, 130+ languages) |
| S34 | https://platform.openai.com/docs/guides/text-to-speech | OpenAI text to speech guide | read 2026-11-13 | Steerable model | "The tts-1 , tts-1-hd , and gpt-4o-mini-tts" / "instructions: \"Speak in a cheerful and positive tone.\"" | confirmed |
| S35 | https://cartesia.ai/pricing | Cartesia pricing | read 2026-11-13 | Free tier | "$0 /mo Start free 20K credits / month" | confirmed |
| S36 | https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/README.md | whisper.cpp README | read 2026-11-13 | Metal on Apple Silicon | "On Apple Silicon, the inference runs fully on the GPU via Metal" | confirmed |
| S37 | https://www.remotion.dev/docs/install-whisper-cpp/ | @remotion/install-whisper-cpp | read 2026-11-13 | Captions in Remotion | "installWhisperCpp() downloadWhisperModel() transcribe() toCaptions()" | confirmed |
| S38 | https://raw.githubusercontent.com/m-bain/whisperX/main/README.md | WhisperX README | 3.8.6, BSD-2-Clause [M] | Word timestamps | "fast automatic speech recognition (70x realtime with large-v2) with word-level timestamps" | confirmed (word-level timestamps, 70x realtime); BSD-2-Clause confirmed on PyPI |
| S39 | https://support.spotify.com/us/artists/article/loudness-normalization/ | Spotify loudness normalization | read 2026-11-13 | -14 LUFS | "We adjust tracks to -14 dB LUFS , according to the ITU 1770 standard." | confirmed |
| S40 | https://support.google.com/youtube/answer/3376882 | YouTube Audio Library help | read 2026-11-13 | CC tracks need credit | "If you're using a track with a Creative Commons license, you must credit the artist in your video's description." | confirmed |
| S41 | https://incompetech.com/music/royalty-free/licenses/ | Incompetech licences | read 2026-11-13 | CC or paid licence | "Standard License For projects where attribution is not wanted or is impossible" | confirmed |
| S42 | https://freemusicarchive.org/License_Guide | FMA License Guide | read 2026-11-13 | Per-track licences | "Most of the music licences you will find on FMA are Creative Commons licences" | confirmed |
| S43 | https://huggingface.co/stabilityai/stable-audio-open-1.0 | Stable Audio Open 1.0 | read 2026-11-13 | Licence limits | "Stability AI Community License . Commercial License : to use this model commercially, please refer to https://stability.ai/license" | confirmed |
| S44 | https://raw.githubusercontent.com/mozman/ezdxf/master/README.md | ezdxf README | read 2026-11-13 | MIT; render DXF to SVG/PNG | "MIT-License" / "matplotlib, which can export images as PNG, PDF or SVG" | confirmed |
| S45 | https://jfly.uni-koeln.de/color/ | Color Universal Design (Okabe, Ito) | read 2026-11-13 | Colour-blind safe palette | "Color Universal Design (CUD) / Colorblind Barrier Free" | partly: page exists and is by Okabe and Ito. The hex values were not on the page and stay [U]. |
| M1 | local: `which`, `--version`, `npm view`, PyPI JSON, GitHub API, `find` | Measurements on this Mac | 2026-11-13 | Versions, stars, release dates, installed tools, dataset file counts | ffmpeg 8.1.1; node v26.13.1; hyperframes 0.9.42; remotion 4.0.543; manim 0.22.1; @motion-canvas/core last release v3.17.2 2024-12-14; macOS 27.0.1, Apple M4 Max | partly: npm and GitHub values re-checked (see Verification); local counts not re-checked |

Note on quotes: a proxy in this environment drops some words from tool output. I re-read each quote from a saved
file to keep it exact; S7 is marked where the proxy text differs.

## Verification

Date: 2026-11-13. Checker: independent fact-check pass, run with `curl` (WebFetch hit a usage limit).

- Sources opened: 45 of 45 URLs (S1 to S45) plus npm, PyPI and GitHub API checks for the M1 version and star numbers. All 45 URLs returned a page.
- Result: 42 confirmed, 3 partly (S1, S16, S45), 0 not found. The M1 measurement row is partly re-checked. No finding rests on a missing source, so no finding is marked UNVERIFIED.
- Caveat: the fetch path drops some short words from page text (as the author noted). Quotes were matched on their content words, not on every word.

Corrections:

1. S1 and finding 1, "What does not work": the FAQ does not call syncing narration "the wrong question". Grant Sanderson writes "I worry when I hear people ask ... 'How do I sync up narration into manim?'" and says to use video-editing software. Text changed.
2. S16, finding 7, style guide: the 37-character line limit in the BBC guide is a broadcast (Teletext) limit. For online video the guide gives a width limit (68% of a 16:9 frame). The 0.3 s per word figure is correct. Text changed; the 37 to 42 characters line is now marked as our own choice [E].
3. S45: the Okabe-Ito page exists, but it does not list the hex values. They stay [U].
4. HyperFrames stars: 83,911 now (was 83,909). Manim licence: MIT confirmed on GitHub (was [U]).

Checked and confirmed without change: HyperFrames Apache-2.0, Node 22+, 9 skills, version 0.9.42; Remotion 4.0.543, free tier text, 13 skills, $25 per seat; Code2Video and TheoremExplainAgent titles, authors, dates, quotes and 93.8%; Kokoro-82M Apache-2.0; Chatterbox retired August 2026 (code stays under MIT); Dia English only, Apache-2.0; ElevenLabs v4 $0.08 and v4 Turbo $0.04 per 1K characters; GSAP free for commercial use; Gemini 3.8 Flash TTS; Motion Canvas 3.17.2 (2024-12-14), Theatre.js 0.7.2 (2024-05), Revideo 0.11.0 (2026-07-10).
Not re-checked: local measurements (installed tools, dataset file counts, `say` voices), the Remotion `still` flags, and all [E] and [U] items.
