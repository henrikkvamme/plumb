# Plumb (Stoa Desk)

The judge-facing UI for the Stoa challenge "Make Blueprints Talk". It shows a drawing as black ink on grey paper,
answers a question with the `bp` agent in `../stoa`, and explains the answer: the confidence and its reasons,
each tool call, and each fact drawn on the sheet.

## Run

```sh
pnpm install
pnpm py     # the drawing agent service on 127.0.0.1:4722 (Python, in the uv environment of ../stoa)
pnpm dev    # the app on port 4725
```

`pnpm py` reads the model keys from the environment or from `py/.env`: `OPENROUTER_API_KEY`, or `AI_ROUTER_BASE_URL` and `AI_ROUTER_API_KEY` for any OpenAI-compatible router. The app calls the service through
`src/server/desk-agent.ts`. Set `DESK_PY_PORT` to move the service.

## Parts

- `py/desk/service.py`: HTTP routes: samples, open a document, a page image, ask, poll a run.
- `py/desk/facts.py`: the things on a drawing with their facts. Swiss vector plans have a reader here. Large scanned sheets use `bp.facts`.
- `py/desk/trace.py` and `py/desk/explain.py`: the tool calls of a run, the source of the answer value, and the confidence from the evidence.
- `py/desk/ink.py`: a page as ink on a transparent sheet, and the wall layer for the shadow and the 3D view.
- `src/domain/desk.ts`, `src/domain/desk-flow.machine.ts`: the schemas and the open, ask and poll flow.
- `src/features/desk/`: the viewer (pan, zoom, 3D), the answer card, the trace and the facts tab.

## Starter notes

The template for a new challenge app. It is built so that coding agents get fast, strict feedback.

- TanStack Start and React 19 on Vite+ (`vp`), with pnpm
- Effect 4 services behind TanStack Start server functions
- XState 6 with `@xstate/effect`, read in React through `@effect/atom-react`
- Oxlint with type-aware rules, the anti-slop rules, a no-comments rule and import fences
- `effect-tsrs` for type checks with Effect diagnostics as errors
- A project CLI, `pnpm j`, for the gate, verification and scaffolding

## Start a new challenge app

```sh
cd starter
pnpm install
pnpm j new project my-challenge
cd ../my-challenge
pnpm install
pnpm j check
pnpm dev
```

`AGENTS.md` has the rules for agents. The lint rules in `tools/oxlint/anti-slop` come from
[dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop) through
[joelhooks/rat-stack](https://github.com/joelhooks/rat-stack), as does `tools/oxlint/no-comments.ts`.
Both sources use the MIT license.
