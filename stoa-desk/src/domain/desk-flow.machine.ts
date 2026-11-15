import { createEffectLogic, setupEffect } from "@xstate/effect";
import { getShortestPaths } from "xstate/graph";
import { Context, Predicate, Schema } from "effect";
import type { Effect } from "effect";

import type { ApiUnavailable } from "./api.ts";
import {
  AskRequest,
  DrawingDocument,
  OpenRequest,
  PollRequest,
  Run,
  Scaled,
  UploadRequest,
  Uploaded,
} from "./desk.ts";
import type { DeskFailed } from "./desk.ts";
import { actorDone, actorFailed, afterDelay, machineChecks } from "./machine-checks.ts";

export class DeskClient extends Context.Service<
  DeskClient,
  {
    readonly ask: (request: AskRequest) => Effect.Effect<Run, DeskFailed | ApiUnavailable>;
    readonly open: (
      request: OpenRequest,
    ) => Effect.Effect<DrawingDocument, DeskFailed | ApiUnavailable>;
    readonly poll: (request: PollRequest) => Effect.Effect<Run, DeskFailed | ApiUnavailable>;
    readonly upload: (
      request: UploadRequest,
    ) => Effect.Effect<Uploaded, DeskFailed | ApiUnavailable>;
  }
>()("stoa-desk/domain/desk-flow.machine/DeskClient") {}

export const pollIntervalMs = 350;

export const missLimit = 4;

export const firstSample = "swiss-1000";

const openTask = createEffectLogic({
  effect: ({ input }) => DeskClient.use((client) => client.open(input)),
  schemas: { input: OpenRequest },
});

const askTask = createEffectLogic({
  effect: ({ input }) => DeskClient.use((client) => client.ask(input)),
  schemas: { input: AskRequest },
});

const pollTask = createEffectLogic({
  effect: ({ input }) => DeskClient.use((client) => client.poll(input)),
  schemas: { input: PollRequest },
});

const uploadTask = createEffectLogic({
  effect: ({ input }) => DeskClient.use((client) => client.upload(input)),
  schemas: { input: UploadRequest, output: Uploaded },
});

const noFile = new File([], "drawing");

const afterRun = (run: Run) => (run.status === "running" ? "waiting" : "settled");

export const deskFlowMachine = setupEffect({
  actors: { askTask, openTask, pollTask, uploadTask },
  schemas: {
    context: Schema.Struct({
      document: Schema.NullOr(DrawingDocument),
      misses: Schema.Finite,
      resent: Schema.Boolean,
      about: Schema.Array(Schema.String),
      question: Schema.String,
      run: Schema.NullOr(Run),
      sample: Schema.String,
      upload: Schema.NullOr(Schema.File),
    }),
    events: {
      ASK: Schema.Struct({ about: Schema.Array(Schema.String), text: Schema.String }),
      CLEAR: Schema.Struct({}),
      OPEN: Schema.Struct({ sample: Schema.String }),
      SCALED: Schema.Struct({ patch: Scaled }),
      RETRY: Schema.Struct({}),
      UPLOAD: Schema.Struct({ file: Schema.File }),
    },
  },
}).createMachine({
  context: {
    about: [],
    document: null,
    misses: 0,
    question: "",
    resent: false,
    run: null,
    sample: firstSample,
    upload: null,
  },
  id: "deskFlow",
  initial: "opening",
  states: {
    askFailed: {
      on: {
        SCALED: ({ context, event }) => ({
          context: {
            document: context.document === null ? null : { ...context.document, ...event.patch },
            question: "",
            run: null,
          },
          target: "ready",
        }),
        ASK: ({ event }) => ({
          context: {
            about: event.about,
            misses: 0,
            question: event.text,
            resent: false,
            run: null,
          },
          target: "starting",
        }),
        CLEAR: () => ({ context: { question: "", run: null }, target: "ready" }),
        OPEN: ({ event }) => ({
          context: { document: null, question: "", run: null, sample: event.sample },
          target: "opening",
        }),
        UPLOAD: ({ event }) => ({
          context: { document: null, question: "", run: null, upload: event.file },
          target: "uploading",
        }),
        RETRY: () => ({ context: { misses: 0, resent: false, run: null }, target: "starting" }),
      },
    },
    openFailed: {
      on: {
        OPEN: ({ event }) => ({
          context: { document: null, question: "", run: null, sample: event.sample },
          target: "opening",
        }),
        UPLOAD: ({ event }) => ({
          context: { document: null, question: "", run: null, upload: event.file },
          target: "uploading",
        }),
        RETRY: { target: "opening" },
      },
    },
    opening: {
      invoke: {
        id: "openTask",
        input: ({ context }) => ({ sample: context.sample }),
        onDone: ({ event }) => ({ context: { document: event.output }, target: "ready" }),
        onError: { target: "openFailed" },
        src: "openTask",
      },
    },
    polling: {
      on: {
        CLEAR: () => ({ context: { question: "", run: null }, target: "ready" }),
      },
      invoke: {
        id: "pollTask",
        input: ({ context }) => ({ runId: context.run?.id ?? "" }),
        onDone: ({ event }) => ({
          context: { misses: 0, run: event.output },
          target: afterRun(event.output),
        }),
        onError: ({ context }) => {
          if (context.misses < missLimit) {
            return { context: { misses: context.misses + 1 }, target: "waiting" };
          }

          return context.resent
            ? { target: "askFailed" }
            : { context: { misses: 0, resent: true }, target: "starting" };
        },
        src: "pollTask",
      },
    },
    ready: {
      on: {
        SCALED: ({ context, event }) => ({
          context: {
            document: context.document === null ? null : { ...context.document, ...event.patch },
            question: "",
            run: null,
          },
          target: "ready",
        }),
        ASK: ({ event }) => ({
          context: {
            about: event.about,
            misses: 0,
            question: event.text,
            resent: false,
            run: null,
          },
          target: "starting",
        }),
        OPEN: ({ event }) => ({
          context: { document: null, question: "", run: null, sample: event.sample },
          target: "opening",
        }),
        UPLOAD: ({ event }) => ({
          context: { document: null, question: "", run: null, upload: event.file },
          target: "uploading",
        }),
      },
    },
    settled: {
      on: {
        SCALED: ({ context, event }) => ({
          context: {
            document: context.document === null ? null : { ...context.document, ...event.patch },
            question: "",
            run: null,
          },
          target: "ready",
        }),
        ASK: ({ event }) => ({
          context: {
            about: event.about,
            misses: 0,
            question: event.text,
            resent: false,
            run: null,
          },
          target: "starting",
        }),
        CLEAR: () => ({ context: { question: "", run: null }, target: "ready" }),
        OPEN: ({ event }) => ({
          context: { document: null, question: "", run: null, sample: event.sample },
          target: "opening",
        }),
        UPLOAD: ({ event }) => ({
          context: { document: null, question: "", run: null, upload: event.file },
          target: "uploading",
        }),
      },
    },
    starting: {
      on: {
        CLEAR: () => ({ context: { question: "", run: null }, target: "ready" }),
      },
      invoke: {
        id: "askTask",
        input: ({ context }) => ({
          about: context.about,
          documentId: context.document?.id ?? "",
          question: context.question,
        }),
        onDone: ({ event }) => ({
          context: { run: event.output },
          target: afterRun(event.output),
        }),
        onError: { target: "askFailed" },
        src: "askTask",
      },
    },
    uploading: {
      invoke: {
        id: "uploadTask",
        input: ({ context }) => ({ file: context.upload ?? noFile }),
        onDone: ({ event }) => ({
          context: { sample: event.output.sample, upload: null },
          target: "opening",
        }),
        onError: { target: "openFailed" },
        src: "uploadTask",
      },
    },
    waiting: {
      on: {
        CLEAR: () => ({ context: { question: "", run: null }, target: "ready" }),
      },
      after: { [pollIntervalMs]: { target: "polling" } },
    },
  },
});

const sampleDocument: DrawingDocument = {
  conflicts: [],
  entities: [],
  id: "doc-1",
  ingestMs: 80,
  kind: "plan_pdf",
  kindLabel: "Vector floor plan (PDF)",
  name: "Sample",
  pages: [{ height: 842, index: 0, unit: "pt", width: 1190 }],
  questions: [],
  samples: [],
  summary: [],
  tools: [],
  unknown: [],
};

const runWith = (status: Run["status"]): Run => ({
  about: [],
  activity: "",
  answer: null,
  documentId: "doc-1",
  elapsedMs: 10,
  error: "",
  id: "run-1",
  question: "Why?",
  status,
  steps: [],
});

const withRun = new Set(["waiting", "polling", "settled"]);

const withDocument = new Set(["ready", "starting", "waiting", "polling", "settled", "askFailed"]);

export const deskFlowChecks = machineChecks({
  invariants: [
    {
      holds: ({ context, value }) =>
        !Predicate.isString(value) || !withDocument.has(value) || context.document !== null,
      name: "a question is asked only about an open document",
    },
    {
      holds: ({ context, value }) =>
        !Predicate.isString(value) || !withRun.has(value) || context.run !== null,
      name: "a run that is polled or settled exists",
    },
    {
      holds: ({ context, value }) => value !== "settled" || context.run?.status !== "running",
      name: "a settled run does not still run",
    },
  ],
  name: "deskFlow",
  reachable: [
    "opening",
    "openFailed",
    "ready",
    "starting",
    "waiting",
    "polling",
    "settled",
    "askFailed",
    "uploading",
  ],
  states: () =>
    getShortestPaths(deskFlowMachine, {
      events: [
        { about: [], text: "Why?", type: "ASK" },
        { type: "RETRY" },
        {
          patch: {
            conflicts: [],
            entities: [],
            kind: sampleDocument.kind,
            kindLabel: sampleDocument.kindLabel,
            pages: sampleDocument.pages,
            summary: [],
            tools: [],
            unknown: [],
          },
          type: "SCALED",
        },
        { type: "CLEAR" },
        { sample: "sheet-dorm", type: "OPEN" },
        { file: new File(["plan"], "plan.png"), type: "UPLOAD" },
        actorDone("uploadTask", { sample: "up-1" }),
        actorFailed("uploadTask"),
        actorDone("openTask", sampleDocument),
        actorFailed("openTask"),
        actorDone("askTask", runWith("running")),
        actorDone("askTask", runWith("answered")),
        actorFailed("askTask"),
        actorDone("pollTask", runWith("running")),
        actorDone("pollTask", runWith("abstained")),
        actorFailed("pollTask"),
        afterDelay("deskFlow.waiting", pollIntervalMs),
      ],
      limit: 20_000,
    }).map((path) => path.state),
  tagOf: ({ value }) => (Predicate.isString(value) ? value : JSON.stringify(value)),
});
