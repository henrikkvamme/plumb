# Agent guide

TanStack Start and React on Vite+, with Effect 4 services, XState 6 machines, UI SDK components and pnpm.
The gate is strict on purpose. A red gate tells you what to fix. Do not ask a person first.

## Commands

- `pnpm dev` starts the app on port 3000 on every interface. It accepts each host name, so a link such as `http://<host>:3000/` works.
- `pnpm j check` is the gate: format, lint, types with Effect diagnostics, machine checks. Run it before each push.
- `pnpm j verify machines` explores each state machine and checks its invariants.
- `pnpm j verify smoke` builds the app and renders the home page on the server.
- `pnpm j verify browser [url]` opens the running app in headless Chrome at desktop size, at phone size (390 px) and with reduced motion. It fails on a console error, an uncaught exception, a failed request or sideways scroll, and writes screenshots to `.verify/`: `<view>.png` shows the first screen and `<view>-full.png` the whole page. Start `pnpm dev` first.
- `pnpm j new feature <name>` creates a schema, an Effect service and a server function that pass the gate.
- `pnpm j new project <name>` copies this starter to `../<name>`.
- `pnpm j gpu types|up|ls|run|ssh|push|pull|down` runs ML training on team GPU VMs on Verda. Read `../infra/verda/README.md`. Delete a VM when you are done.
- `pnpm build && pnpm start` runs the production server on port 3000. The `Dockerfile` runs the same server. To host the app, read `../docs/hosting.md`.
- `pnpm fix` applies lint fixes, then formats. It formats also when lint finds an error it cannot fix.

## Layout and fences

Lint enforces these import rules. `ask` is the example for each layer.

- `src/domain`: schemas, tagged errors, service tags and machines. Pure. No IO, no React.
- `src/server`: Effect services with a static `layer`. Add each layer to `AppLayer` in `src/server/runtime.ts`.
- `src/api`: server functions. Each one validates input with a Schema and calls one service through `runApi`.
- `src/features`, `src/routes`, `src/components`: UI. These call `src/api` and never import `src/server`.

## Rules

- Read the docs that ship with the installed versions: `node_modules/effect/AGENTS.md`, `node_modules/effect/ai-docs`, `node_modules/xstate/docs/agents.md`, `node_modules/vite-plus/AGENTS.md`. Your memory of Effect 3 and XState 5 is wrong here.
- Write Effect code with `Effect.fn("Service.method")` and `Effect.gen`. Define errors with `Schema.TaggedError`. Send errors across the server boundary with `runApi` and `fromApi`.
- A flow with more than two steps, async work or a retry is a state machine in `src/domain/<name>.machine.ts`. Write the machine and its `machineChecks` first. Make `pnpm j verify machines` pass. Then build the service and the UI around it. Add the checks to `src/domain/machines.ts`.
- In `machineChecks`, make system events with the helpers in `src/domain/machine-checks.ts`: `afterDelay("<machineId>.<state>", <ms>)` for an `after` timer, `actorDone("<invokeId>", output)` and `actorFailed("<invokeId>", error)` for an invoked actor. Pass the error when `onError` reads `event.error`, such as `new EffectFailure(Cause.fail(new MyError(...)))`, or the traversal crashes on `undefined`.
- An app with no server keeps `src/server/runtime.ts`. To remove the `ask` example, delete its files in `src/domain`, `src/server`, `src/api` and `src/features`, remove `Answerer.layer` from `AppLayer`, and remove `askFlowChecks` from `src/domain/machines.ts`.
- A CSS custom property in a `style` prop is typed: `style={{ "--i": 2 }}`. A shader or query string can carry a language tag: `/* glsl */` before the template string.
- Build interactive UI with UI SDK: `@ui-sdk/react`, one import per component, such as `@ui-sdk/react/select`. Do not hand-roll a dialog, menu, select, combobox, tabs, toast or form field, and do not add shadcn or Radix. Before you use it, read `node_modules/@ui-sdk/react/docs/llms.txt` and `node_modules/@ui-sdk/core/skills/ui-sdk/SKILL.md`. For a new component, also read `core.md` and `rendering.md` in that docs directory. Our rule against tests overrides the skill's rule that each task gets tests.
- `@ui-sdk/core/web.css` gives the default look. Theme it with the `--ui-*` tokens on `:root` in `src/styles.css`. Add layout with Tailwind classes. Keep the `@layer` line at the top of `src/styles.css`: it puts `ui-sdk` above the Tailwind reset and below the utilities.
- Do not write unit tests. Put the effort into types, schemas, machine invariants, lint rules and fences. Prove behavior with `pnpm j verify`. For each change a person can see, run `pnpm j verify browser` and look at each screenshot in `.verify/`: a broken shader, a missing file and a wide element all pass the gate. A screenshot from a tab in the background can be black, and a headed browser window cannot be narrower than 500 px, so use this command for the phone view.
- Do not write comments. Names and types carry the meaning.
- Do not weaken a check to get a green result. No `any`, no `as` without a `SAFETY:` reason, no disabled rule. If a rule is wrong for the product, say so and change the rule in one commit of its own.
- A heading with one element per letter has the full text in one screen-reader-only `span`, and the letters in a wrapper with `aria-hidden="true"`. Do not put `role="text"` or `role="img"` on the heading: lint rejects both.
- Keep the text of an input in React state and send it to a machine on submit or on change. An input whose `value` comes from the actor's snapshot drops keystrokes, because each key goes through the machine and comes back late.
- When a feature needs a new way to prove it works, add a `verify` subcommand in `tools/cli/main.ts`.

## Improve the fence

The fence is the set of checks that reject wrong code: types, Effect diagnostics, lint rules, import fences, machine checks and `verify` commands.
A mistake that cost you a failed run, a red gate you did not expect, or a correction from a person must not be possible a second time.

- Before you finish a task, list each such mistake. Encode each one at the highest level that can hold it:
  1. Stack: change the template, a default, a script or a helper so the mistake has no place to occur.
  2. Types: a Schema, a branded type or a stricter signature.
  3. Lint: a rule in `tools/oxlint` or a fence in `vite.config.ts`. Put the fix in the message.
  4. Verify: a `verify` subcommand that fails on the mistake.
  5. Context: one line in this file. Use this level only when no check can hold the rule.
- Make the change in `../starter` also when it helps every app. Commit it apart from the feature, with the mistake in the commit message.
- Prove the new check: write the wrong code once, see the gate fail with a message that names the fix, then remove it.
- A red gate ends with a reminder of this section. It is not noise: answer it. Either the failure was expected, or you add a check or a clearer message.
- A rule that rejects correct code is also a defect. Narrow the rule. Do not work around it in the product code.

## How we work

- Exploring: one agent, one loop. No subagents, no review.
- Building from a spec: Fable 5.2 plans and leads. Opus 5.5 implements one unit each.
- A spec has: the goal, one command that proves it, the files to edit, and the types and machines fixed first.
- Parallel workers need disjoint files. Do not split steps that depend on each other.
- Fable 5.2 takes hard problems, planning, 3D and video.
- Review: one round on the diff by GPT-6.1 Sol or GPT-6 Astra. Run `pnpm j check` first. Fix real defects only.
- Push to `main` often. No PRs. Run `pnpm j check`, then `git pull --rebase`, then push.
