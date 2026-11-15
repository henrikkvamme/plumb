import { createServerFn } from "@tanstack/react-start";
import { Schema } from "effect";

import {
  AskRequest,
  DeskFailed,
  OpenRequest,
  PollRequest,
  RemoveRequest,
  ScaleRequest,
  TranslateRequest,
} from "#/domain/desk.ts";
import { DeskAgent } from "#/server/desk-agent.ts";
import { runApi } from "#/server/runtime.ts";

export const openSample = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(OpenRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.open(data))));

export const askQuestion = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(AskRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.ask(data))));

export const translateDrawing = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(TranslateRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.translate(data))));

export const removeDrawing = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(RemoveRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.remove(data))));

export const pollRun = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(PollRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.poll(data))));

export const setScale = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(ScaleRequest))
  .handler(({ data }) => runApi(DeskFailed)(DeskAgent.use((agent) => agent.scale(data))));
