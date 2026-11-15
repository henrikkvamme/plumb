# Plumb

Plumb answers questions about construction drawings. Each answer shows the measurement it comes from, so you can check it.

Live demo: https://plumb.henrikkvamme.no/

Plumb is our entry for the Stoa challenge "Make Blueprints Talk" at Junction 2026.

## How it works

1. Plumb detects the kind of document: a vector plan, a scanned sheet, a CAD file or an IFC model. A small language model gets only the tools for that kind.
2. Deterministic tools measure the drawing: scales, printed areas, wall lines, rooms, doors and symbols.
3. A CHECK state refuses a number that no tool measured. After two refusals, the agent gives no answer.
4. Each answer shows its evidence on the drawing, the tool steps, and a confidence. The confidence is the 95% lower bound of the measured track record for that kind of question.

## Run

You need Node.js, pnpm and [uv](https://docs.astral.sh/uv/).

```sh
cd stoa-desk
pnpm install
pnpm py     # the drawing agent service on 127.0.0.1:4722, in the uv environment of ../stoa
pnpm dev    # the app on port 4725
```

Set the model keys in the environment, or in `stoa-desk/py/.env`:

- `OPENROUTER_API_KEY`, or
- `AI_ROUTER_BASE_URL` and `AI_ROUTER_API_KEY` for another OpenAI-compatible router.

`BP_AGENT_MODEL` sets the agent model. `DESK_PY_PORT` moves the service.

## Results

The full numbers are in [`stoa/docs/RESULTS.md`](stoa/docs/RESULTS.md).

- Printed areas and scales on held-out large sheets: 80 of 82 right, 0 wrong.
- All questions on 30 held-out large sheets (160 questions): 76% right, 4.4% wrong. The agent gives no answer on the rest.
- Cost and time: about 0.1 cent and 5 to 6 seconds per question with `claude-haiku-5.5`.

## Known failures

- Door counts on scans are an estimate. The agent marks them as an estimate, or gives no answer.
- Door counts on held-out sheets of other building kinds are weaker than on the development sheets.
- Room areas on photos with perspective can be wrong. Bleed-through on scans affects door counts.
- Questions about a whole IFC model cannot be answered from one storey sheet.
- Free-text answers with no number are not scored.
- The target of +0.80 score with at most 3% wrong on held-out sheets is not met.

## Layout

- `stoa-desk/`: the web app (TanStack Start and React) and `stoa-desk/py/`, the Python service that runs the agent.
- `stoa-desk/py/samples/`: small sample drawings for the app.
- `stoa/src/bp/`: the drawing agent `bp` and its measurement tools.
- `stoa/tests/`: tests for `bp`.
- `stoa/jobs/`: training jobs for the detectors.
- `stoa/analysis/`, `stoa/experiments/`: evaluation design and the experiment ledger.
- `stoa/docs/`: results, evaluation method and research notes.
