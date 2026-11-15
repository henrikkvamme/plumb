import { NodeRuntime, NodeServices } from "@effect/platform-node";
import { Console, Effect, FileSystem, Path, Predicate, Schema } from "effect";
import { Argument, Command } from "effect/cli";
import { FetchHttpClient } from "effect/http";
import { ChildProcess, ChildProcessSpawner } from "effect/process";

import { allMachineChecks } from "#/domain/machines.ts";

import type { BrowserFailed } from "./browser.ts";
import { verifyBrowser } from "./browser.ts";
import type { GpuFailed } from "./gpu.ts";
import { gpu } from "./gpu.ts";
import { featureFiles } from "./templates.ts";

class CheckFailed extends Schema.TaggedError<CheckFailed>()("CheckFailed", {
  check: Schema.String,
}) {}

const KebabName = Schema.String.check(
  Schema.isPattern(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/u, {
    message: "Expected a kebab-case name such as `pitch-list`",
  }),
);

const starterRoot = Effect.fn("cli.starterRoot")(function* starterRoot() {
  const path = yield* Path.Path;

  return path.resolve(import.meta.dirname, "../..");
});

const run = Effect.fn("cli.run")(function* run(command: string, args: readonly string[]) {
  const spawner = yield* ChildProcessSpawner.ChildProcessSpawner;
  const cwd = yield* starterRoot();

  const handle = yield* spawner.spawn(
    ChildProcess.make(command, [...args], {
      cwd,
      stderr: "inherit",
      stdout: "inherit",
    }),
  );

  const exitCode = yield* handle.exitCode;

  if (exitCode !== 0) {
    return yield* new CheckFailed({ check: [command, ...args].join(" ") });
  }
}, Effect.scoped);

const ServerModule = Schema.Struct({
  default: Schema.Struct({
    fetch: Schema.declare((value): value is (request: Request) => Promise<Response> =>
      Predicate.isFunction(value),
    ),
  }),
});

const renderHome = Effect.fn("cli.renderHome")(function* renderHome() {
  const path = yield* Path.Path;
  const root = yield* starterRoot();
  const serverUrl = yield* path.toFileUrl(path.join(root, "dist/server/server.js"));

  const server = yield* Effect.tryPromise({
    catch: () => new CheckFailed({ check: "smoke: load dist/server/server.js" }),
    try: () => import(serverUrl.href).then(Schema.decodeUnknownPromise(ServerModule)),
  });

  const response = yield* Effect.tryPromise({
    catch: () => new CheckFailed({ check: "smoke: GET /" }),
    try: () => server.default.fetch(new Request("http://localhost/")),
  });

  const html = yield* Effect.tryPromise({
    catch: () => new CheckFailed({ check: "smoke: read the response body" }),
    try: () => response.text(),
  });

  if (response.status !== 200 || !html.includes("<main")) {
    yield* Console.error(
      `smoke: GET / returned ${response.status}. Fix: run \`pnpm dev\` and read the server error.`,
    );

    return yield* new CheckFailed({ check: "smoke" });
  }

  yield* Console.log("ok smoke: GET / returned 200 with a <main> element");
});

const machines = Command.make(
  "machines",
  {},
  Effect.fn("cli.machines")(function* machines() {
    const reports = allMachineChecks.map((checks) => checks.run());

    for (const report of reports) {
      const status = report.failures.length === 0 ? "ok" : "FAIL";

      yield* Console.log(
        `${status} machine ${report.name}: ${report.statesExplored} states explored`,
      );

      for (const failure of report.failures) {
        yield* Console.error(`  ${failure}`);
      }
    }

    if (reports.some((report) => report.failures.length > 0)) {
      yield* Console.error(
        "Fix: change the machine, not the check. A check changes only when the product rule changes.",
      );

      return yield* new CheckFailed({ check: "machines" });
    }
  }),
).pipe(
  Command.withDescription(
    "Explore each state machine and check its invariants and reachable states",
  ),
);

const smoke = Command.make(
  "smoke",
  {},
  Effect.fn("cli.smoke")(function* smoke() {
    yield* run("vp", ["build", "--logLevel", "warn"]);
    yield* renderHome();
  }),
).pipe(Command.withDescription("Build the app and render the home page on the server"));

const browser = Command.make(
  "browser",
  {
    url: Argument.String("url").pipe(
      Argument.withDescription("Page to open. Default: the dev server"),
      Argument.withDefault("http://localhost:3000/"),
    ),
  },
  Effect.fn("cli.browser")(function* browser({ url }) {
    yield* verifyBrowser(url, yield* starterRoot());
  }),
).pipe(
  Command.withDescription(
    "Open the page in headless Chrome at desktop and phone size: no console error, no failed request, no sideways scroll. Writes screenshots to .verify/",
  ),
);

const verify = Command.make("verify").pipe(
  Command.withDescription("Checks that prove behavior. Run them before you say a feature works."),
  Command.withSubcommands([machines, smoke, browser]),
);

const check = Command.make(
  "check",
  {},
  Effect.fn("cli.check")(function* check() {
    yield* run("vp", ["fmt", "--check"]);
    yield* run("vp", ["lint", "--deny-warnings"]);
    yield* run("effect-tsrs", ["--project", "tsconfig.json", "--strict", "--type-check"]);
    yield* run("node", ["tools/cli/main.ts", "verify", "machines"]);
  }),
).pipe(Command.withDescription("The gate: format, lint, types with Effect diagnostics, machines"));

const feature = Command.make(
  "feature",
  {
    name: Argument.String("name").pipe(
      Argument.withDescription("Feature name in kebab-case"),
      Argument.withSchema(KebabName),
    ),
  },
  Effect.fn("cli.new.feature")(function* feature({ name }) {
    const fs = yield* FileSystem.FileSystem;
    const path = yield* Path.Path;
    const root = yield* starterRoot();
    const packageName = path.basename(root);

    for (const file of featureFiles(name, packageName)) {
      const target = path.join(root, file.path);

      if (yield* fs.exists(target)) {
        yield* Console.error(`${file.path} exists. Fix: pick another name or edit that file.`);

        return yield* new CheckFailed({ check: "new feature" });
      }

      yield* fs.writeFileString(target, file.content);
      yield* Console.log(`created ${file.path}`);
    }

    yield* Console.log(
      `Next: add the service layer to \`AppLayer\` in src/server/runtime.ts, then build the UI in src/features/${name}/.`,
    );
  }),
).pipe(
  Command.withDescription("Create the domain schema, the Effect service and the server function"),
);

const project = Command.make(
  "project",
  {
    name: Argument.String("name").pipe(
      Argument.withDescription("Directory name of the new challenge, in kebab-case"),
      Argument.withSchema(KebabName),
    ),
  },
  Effect.fn("cli.new.project")(function* project({ name }) {
    const fs = yield* FileSystem.FileSystem;
    const path = yield* Path.Path;
    const root = yield* starterRoot();
    const starterName = path.basename(root);
    const target = path.resolve(root, "..", name);

    if (yield* fs.exists(target)) {
      yield* Console.error(`${target} exists. Fix: pick another name.`);

      return yield* new CheckFailed({ check: "new project" });
    }

    yield* run("rsync", [
      "-a",
      "--exclude=node_modules",
      "--exclude=dist",
      "--exclude=.tanstack",
      `${root}/`,
      `${target}/`,
    ]);

    const sourceFiles = yield* fs.readDirectory(path.join(target, "src"), { recursive: true });

    const renamed = [
      "package.json",
      ...sourceFiles
        .filter((file) => file.endsWith(".ts") || file.endsWith(".tsx"))
        .map((file) => path.join("src", file)),
    ];

    for (const file of renamed) {
      const absolute = path.join(target, file);
      const content = yield* fs.readFileString(absolute);

      yield* fs.writeFileString(
        absolute,
        content
          .replaceAll(`"${starterName}/`, `"${name}/`)
          .replaceAll(`"name": "${starterName}"`, `"name": "${name}"`),
      );
    }

    yield* Console.log(`created ${target}`);
    yield* Console.log(`Next: cd ../${name} && pnpm install && pnpm j check && pnpm dev`);
  }),
).pipe(Command.withDescription("Copy this starter to a new challenge directory next to it"));

const create = Command.make("new").pipe(
  Command.withDescription("Scaffold code that already passes the gate"),
  Command.withSubcommands([feature, project]),
);

const fail = (message: string) =>
  Console.error(`FAILED: ${message}`).pipe(
    Effect.andThen(
      Effect.sync(() => {
        process.exitCode = 1;
      }),
    ),
  );

const failGate = (message: string) =>
  fail(message).pipe(
    Effect.andThen(
      Console.error(
        'After the fix: if you did not expect this failure, a check is missing or its message is unclear. Encode it before you finish: read "Improve the fence" in AGENTS.md.',
      ),
    ),
  );

const main = Command.make("j").pipe(
  Command.withDescription("Project CLI: the gate, verification, scaffolding and GPU VMs"),
  Command.withSubcommands([check, verify, create, gpu]),
  Command.run({ version: "0.1.0" }),
  Effect.catchTags({
    CheckFailed: (failure: CheckFailed) => failGate(failure.check),
    BrowserFailed: (failure: BrowserFailed) => failGate(failure.message),
    GpuFailed: (failure: GpuFailed) => fail(failure.message),
  }),
  Effect.provide([NodeServices.layer, FetchHttpClient.layer]),
);

NodeRuntime.runMain(main);
