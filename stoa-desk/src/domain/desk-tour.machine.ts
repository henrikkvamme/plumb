import { setupEffect } from "@xstate/effect";
import { getShortestPaths } from "xstate/graph";
import { Predicate, Schema } from "effect";

import { machineChecks } from "./machine-checks.ts";

export const tourSteps = ["pick", "ask", "answering", "trust", "own"] as const;

export type TourStep = (typeof tourSteps)[number];

const opened = Schema.Struct({ documentId: Schema.String });

export const deskTourMachine = setupEffect({
  schemas: {
    context: Schema.Struct({ answered: Schema.Boolean, documentId: Schema.String }),
    events: {
      ANSWERED: Schema.Struct({}),
      ASKED: Schema.Struct({}),
      CLEARED: Schema.Struct({}),
      FAILED: Schema.Struct({}),
      NEXT: Schema.Struct({}),
      OPENED: opened,
      PICKED: Schema.Struct({}),
      RESTART: opened,
      SKIP: Schema.Struct({}),
      START: opened,
      UNPICKED: Schema.Struct({}),
    },
  },
}).createMachine({
  context: { answered: false, documentId: "" },
  id: "deskTour",
  initial: "idle",
  on: {
    RESTART: ({ event }) => ({
      context: { answered: false, documentId: event.documentId },
      target: ".pick",
    }),
  },
  states: {
    answering: {
      on: {
        ANSWERED: () => ({ context: { answered: true }, target: "trust" }),
        CLEARED: { target: "ask" },
        FAILED: { target: "ask" },
        OPENED: ({ context, event }) =>
          event.documentId === context.documentId
            ? undefined
            : { context: { documentId: event.documentId }, target: "pick" },
        SKIP: { target: "skipped" },
      },
    },
    ask: {
      on: {
        ASKED: { target: "answering" },
        OPENED: ({ context, event }) =>
          event.documentId === context.documentId
            ? undefined
            : { context: { documentId: event.documentId }, target: "pick" },
        SKIP: { target: "skipped" },
        UNPICKED: { target: "pick" },
      },
    },
    done: {},
    idle: {
      on: {
        START: ({ event }) => ({ context: { documentId: event.documentId }, target: "pick" }),
      },
    },
    own: {
      on: {
        NEXT: { target: "done" },
        OPENED: ({ context, event }) =>
          event.documentId === context.documentId ? undefined : { target: "done" },
        SKIP: { target: "skipped" },
      },
    },
    pick: {
      on: {
        ASKED: { target: "answering" },
        OPENED: ({ context, event }) =>
          event.documentId === context.documentId
            ? undefined
            : { context: { documentId: event.documentId }, target: "pick" },
        PICKED: { target: "ask" },
        SKIP: { target: "skipped" },
      },
    },
    skipped: {},
    trust: {
      on: {
        CLEARED: { target: "own" },
        NEXT: { target: "own" },
        OPENED: ({ context, event }) =>
          event.documentId === context.documentId ? undefined : { target: "done" },
        SKIP: { target: "skipped" },
      },
    },
  },
});

const active = new Set<string>(tourSteps);

const afterAnswer = new Set(["trust", "own"]);

export const deskTourChecks = machineChecks({
  invariants: [
    {
      holds: ({ context, value }) =>
        !Predicate.isString(value) || !active.has(value) || context.documentId !== "",
      name: "a tour step belongs to an open drawing",
    },
    {
      holds: ({ context, value }) =>
        !Predicate.isString(value) || !afterAnswer.has(value) || context.answered,
      name: "the trust step comes only after a real answer",
    },
  ],
  name: "deskTour",
  reachable: ["idle", ...tourSteps, "done", "skipped"],
  states: () =>
    getShortestPaths(deskTourMachine, {
      events: [
        { documentId: "doc-1", type: "START" },
        { documentId: "doc-1", type: "RESTART" },
        { documentId: "doc-1", type: "OPENED" },
        { documentId: "doc-2", type: "OPENED" },
        { type: "PICKED" },
        { type: "UNPICKED" },
        { type: "ASKED" },
        { type: "ANSWERED" },
        { type: "FAILED" },
        { type: "CLEARED" },
        { type: "NEXT" },
        { type: "SKIP" },
      ],
      limit: 2000,
    }).map((path) => path.state),
  tagOf: ({ value }) => (Predicate.isString(value) ? value : JSON.stringify(value)),
});
