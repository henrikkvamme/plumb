import { once } from "node:events";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import { Config, Console, Effect, Option, Predicate, Random, Schema } from "effect";
import { HttpClient } from "effect/http";
import { ChildProcess, ChildProcessSpawner } from "effect/process";

export class BrowserFailed extends Schema.TaggedError<BrowserFailed>()("BrowserFailed", {
  message: Schema.String,
}) {}

interface View {
  readonly height: number;
  readonly mobile: boolean;
  readonly name: string;
  readonly reducedMotion: boolean;
  readonly scale: number;
  readonly width: number;
}

const views: readonly View[] = [
  { height: 900, mobile: false, name: "desktop", reducedMotion: false, scale: 1, width: 1440 },
  { height: 844, mobile: true, name: "phone", reducedMotion: false, scale: 2, width: 390 },
  {
    height: 900,
    mobile: false,
    name: "reduced-motion",
    reducedMotion: true,
    scale: 1,
    width: 1440,
  },
];

const browserPaths = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/run/current-system/sw/bin/chromium",
  "/run/current-system/sw/bin/google-chrome-stable",
];

const Target = Schema.Struct({ webSocketDebuggerUrl: Schema.String });

const Message = Schema.Struct({
  id: Schema.optional(Schema.Finite),
  method: Schema.optional(Schema.String),
  params: Schema.optional(
    Schema.Struct({
      args: Schema.optional(
        Schema.Array(
          Schema.Struct({
            description: Schema.optional(Schema.String),
            value: Schema.optional(Schema.Unknown),
          }),
        ),
      ),
      canceled: Schema.optional(Schema.Boolean),
      errorText: Schema.optional(Schema.String),
      exceptionDetails: Schema.optional(
        Schema.Struct({
          exception: Schema.optional(
            Schema.Struct({ description: Schema.optional(Schema.String) }),
          ),
          text: Schema.String,
        }),
      ),
      response: Schema.optional(Schema.Struct({ status: Schema.Finite, url: Schema.String })),
      type: Schema.optional(Schema.String),
    }),
  ),
  result: Schema.optional(
    Schema.Struct({
      data: Schema.optional(Schema.String),
      result: Schema.optional(Schema.Struct({ value: Schema.optional(Schema.Unknown) })),
    }),
  ),
});

type Message = typeof Message.Type;

const Envelope = Schema.Struct({ id: Schema.optional(Schema.Finite) });

const decodeDetail = Schema.decodeUnknownOption(Schema.fromJsonString(Message));

const decodeEnvelope = Schema.decodeUnknownOption(Schema.fromJsonString(Envelope));

const decodeMessage = (text: string): readonly Message[] =>
  Option.toArray(Option.orElse(decodeDetail(text), () => decodeEnvelope(text)));

const decodeTarget = Schema.decodeUnknownPromise(Target);

const problemOf = (message: Message): readonly string[] => {
  const { method, params } = message;

  if (params === undefined) {
    return [];
  }

  if (method === "Runtime.consoleAPICalled" && params.type === "error") {
    const text = (params.args ?? [])
      .map((arg) => (Predicate.isString(arg.value) ? arg.value : (arg.description ?? "")))
      .join(" ");

    return [`console.error: ${text.slice(0, 400)}`];
  }

  if (method === "Runtime.exceptionThrown" && params.exceptionDetails !== undefined) {
    const { exception, text } = params.exceptionDetails;

    return [`uncaught: ${exception?.description ?? text}`.slice(0, 400)];
  }

  if (
    method === "Network.responseReceived" &&
    params.response !== undefined &&
    params.response.status >= 400
  ) {
    return [`HTTP ${params.response.status}: ${params.response.url}`];
  }

  if (method === "Network.loadingFailed" && params.canceled !== true) {
    return [`request failed: ${params.errorText ?? "unknown error"}`];
  }

  return [];
};

const openSession = async (socketUrl: string) => {
  const socket = new WebSocket(socketUrl);
  const messages: Message[] = [];
  let sent = 0;

  socket.addEventListener("message", (event) => {
    messages.push(...decodeMessage(String(event.data)));
  });

  await once(socket, "open");

  const reply = async (id: number, method: string, attempts: number): Promise<Message> => {
    const found = messages.find((message) => message.id === id);

    if (found !== undefined) {
      return found;
    }

    if (attempts <= 0) {
      throw new Error(`The browser did not answer ${method}`);
    }

    await sleep(20);

    return await reply(id, method, attempts - 1);
  };

  return {
    close: () => {
      socket.close();
    },
    problems: () => messages.flatMap(problemOf),
    send: async (
      method: string,
      params: Readonly<
        Record<
          string,
          | boolean
          | number
          | string
          | Readonly<Record<string, number>>
          | readonly Readonly<Record<string, string>>[]
        >
      >,
      attempts = 1000,
    ) => {
      sent += 1;
      socket.send(JSON.stringify({ id: sent, method, params }));

      return await reply(sent, method, attempts);
    },
  };
};

const overflowScript =
  "document.documentElement.scrollWidth - document.documentElement.clientWidth";

interface Run {
  readonly directory: string;
  readonly port: number;
  readonly url: string;
}

const inspectView = async (view: View, { directory, port, url }: Run) => {
  const created = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" });
  const target = await decodeTarget(await created.json());
  const session = await openSession(target.webSocketDebuggerUrl);

  await session.send("Runtime.enable", {});
  await session.send("Network.enable", {});
  await session.send("Page.enable", {});

  await session.send("Emulation.setDeviceMetricsOverride", {
    deviceScaleFactor: view.scale,
    height: view.height,
    mobile: view.mobile,
    width: view.width,
  });

  if (view.reducedMotion) {
    await session.send("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
  }

  await session.send("Page.navigate", { url });
  await sleep(4000);

  const overflow = await session.send("Runtime.evaluate", {
    expression: overflowScript,
    returnByValue: true,
  });

  const data = await session
    .send("Page.captureScreenshot", { format: "png" }, 400)
    .then((shot) => shot.result?.data ?? "")
    .catch(() => "");

  const file = path.join(directory, `${view.name}.png`);

  await writeFile(file, Buffer.from(data, "base64"));

  const fullHeight = await session.send("Runtime.evaluate", {
    expression: "document.documentElement.scrollHeight",
    returnByValue: true,
  });

  const pageHeight = fullHeight.result?.result?.value;

  const full = await session
    .send(
      "Page.captureScreenshot",
      {
        captureBeyondViewport: true,
        clip: {
          height: Predicate.isNumber(pageHeight) ? Math.min(pageHeight, 16_000) : view.height,
          scale: 1,
          width: view.width,
          x: 0,
          y: 0,
        },
        format: "png",
      },
      400,
    )
    .then((shot) => shot.result?.data ?? "")
    .catch(() => "");

  if (full !== "") {
    await writeFile(path.join(directory, `${view.name}-full.png`), Buffer.from(full, "base64"));
  }

  session.close();

  const unpainted =
    data === "" ? ["no screenshot: the page did not paint a frame in 8 seconds"] : [];

  const sideways = overflow.result?.result?.value;

  const scroll =
    Predicate.isNumber(sideways) && sideways > 1
      ? [`the page scrolls sideways by ${sideways}px at ${view.width}px width`]
      : [];

  return { file, problems: [...session.problems(), ...scroll, ...unpainted], view: view.name };
};

type ViewReport = Awaited<ReturnType<typeof inspectView>>;

const inspectViews = async (remaining: readonly View[], run: Run): Promise<ViewReport[]> => {
  const [view, ...rest] = remaining;

  if (view === undefined) {
    return [];
  }

  const report = await inspectView(view, run);

  return [report, ...(await inspectViews(rest, run))];
};

const waitForBrowser = async (port: number, attempts: number): Promise<boolean> => {
  const ready = await fetch(`http://127.0.0.1:${port}/json/version`)
    .then((response) => response.ok)
    .catch(() => false);

  if (ready || attempts <= 0) {
    return ready;
  }

  await sleep(250);

  return await waitForBrowser(port, attempts - 1);
};

export const verifyBrowser = Effect.fn("cli.verifyBrowser")(function* verifyBrowser(
  url: string,
  root: string,
) {
  const spawner = yield* ChildProcessSpawner.ChildProcessSpawner;

  const chromePath = yield* Config.String("CHROME_PATH").pipe(Config.withDefault(""));

  const executable = [chromePath, ...browserPaths].find(
    (candidate) => candidate !== "" && existsSync(candidate),
  );

  if (executable === undefined) {
    return yield* new BrowserFailed({
      message:
        "browser: no Chrome, Brave, Chromium or Edge found. Fix: set CHROME_PATH to a Chromium browser.",
    });
  }

  const reachable = yield* HttpClient.get(url).pipe(
    Effect.map((response) => response.status < 400),
    Effect.orElseSucceed(() => false),
  );

  if (!reachable) {
    return yield* new BrowserFailed({
      message: `browser: ${url} does not answer. Fix: run \`pnpm dev\` in another shell, or pass the URL.`,
    });
  }

  const port = yield* Random.nextIntBetween(9300, 9900);
  const profile = yield* Effect.promise(() => mkdtemp(path.join(tmpdir(), "j-verify-")));
  const directory = path.join(root, ".verify");

  yield* Effect.addFinalizer(() =>
    Effect.promise(() => rm(profile, { force: true, maxRetries: 5, recursive: true })),
  );

  yield* spawner.spawn(
    ChildProcess.make(
      executable,
      [
        "--headless=new",
        `--remote-debugging-port=${port}`,
        `--user-data-dir=${profile}`,
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        "--enable-unsafe-swiftshader",
        "about:blank",
      ],
      { stderr: "ignore", stdout: "ignore" },
    ),
  );

  const started = yield* Effect.promise(() => waitForBrowser(port, 60));

  if (!started) {
    return yield* new BrowserFailed({
      message: `browser: ${executable} did not start. Fix: set CHROME_PATH to another Chromium browser.`,
    });
  }

  yield* Effect.promise(() => mkdir(directory, { recursive: true }));

  const reports = yield* Effect.tryPromise({
    catch: (cause) => new BrowserFailed({ message: `browser: ${String(cause)}` }),
    try: () => inspectViews(views, { directory, port, url }),
  });

  for (const report of reports) {
    const status = report.problems.length === 0 ? "ok" : "FAIL";

    yield* Console.log(`${status} browser ${report.view}: ${report.file}`);

    for (const problem of new Set(report.problems)) {
      yield* Console.error(`  ${problem}`);
    }
  }

  if (reports.some((report) => report.problems.length > 0)) {
    return yield* new BrowserFailed({
      message:
        "browser: the page has errors. Fix: remove each error above. Then look at the screenshots in .verify/.",
    });
  }

  yield* Console.log("Next: look at each screenshot in .verify/ before you say the page works.");
}, Effect.scoped);
