# Stoa research (13 November 2026, 22:00)

A research workflow made these files: one Fable 5.2 ideation agent, six Opus research agents with web search, and one Fable 5.2 synthesis agent.

- `weekend-plan.md`: the ranked approaches, the architecture, the Verda training plan, the timeline, the citations and the questions for Stoa.
- `concepts.md`: 12 solution concepts and 10 open research questions.
- `research-tracks.json`: the findings per track, with source URLs.
- `question-set.html`: example questions from the preview dataset, with the drawings.

Notes:
- The agents had no shell, so the plan's "measured" figures (for example 97% on Swiss rules, 95% template coverage) are not measured. Measure them again before you use them.
- The plan used preview figures. The full set has 127,044 questions on 5,939 drawings. cubicasa5k has 85,514 of them (67%).
- The full question file is now local, so we can exclude every CubiCasa drawing that has a Stoa question from training.
