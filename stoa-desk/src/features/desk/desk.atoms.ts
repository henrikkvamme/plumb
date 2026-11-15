import { createActorAtoms } from "@xstate/effect/atom";
import { Effect, Layer, Schema } from "effect";
import { FetchHttpClient, HttpClient, HttpClientRequest } from "effect/http";
import { Atom } from "effect/reactivity";

import { askQuestion, openSample, pollRun } from "#/api/desk.ts";
import { ApiUnavailable, fromApi } from "#/domain/api.ts";
import { DeskFailed, Uploaded } from "#/domain/desk.ts";
import type { AskRequest, OpenRequest, PollRequest, UploadRequest } from "#/domain/desk.ts";
import { DeskClient, deskFlowMachine } from "#/domain/desk-flow.machine.ts";

const Refusal = Schema.Struct({ reason: Schema.String });

const unavailable = (cause: unknown) => new ApiUnavailable({ cause });

const DeskClientLive = Layer.effect(
  DeskClient,
  Effect.gen(function* make() {
    const http = yield* HttpClient.HttpClient;

    return {
      ask: Effect.fn("DeskClient.ask")((request: AskRequest) =>
        fromApi(DeskFailed)(() => askQuestion({ data: request })),
      ),
      open: Effect.fn("DeskClient.open")((request: OpenRequest) =>
        fromApi(DeskFailed)(() => openSample({ data: request })),
      ),
      poll: Effect.fn("DeskClient.poll")((request: PollRequest) =>
        fromApi(DeskFailed)(() => pollRun({ data: request })),
      ),
      upload: Effect.fn("DeskClient.upload")(function* upload(request: UploadRequest) {
        const bytes = yield* Effect.tryPromise({
          catch: unavailable,
          try: () => request.file.arrayBuffer(),
        });

        const response = yield* http
          .execute(
            HttpClientRequest.post(`${globalThis.location.origin}/api/upload`).pipe(
              HttpClientRequest.setUrlParam("name", request.file.name),
              HttpClientRequest.bodyUint8Array(new Uint8Array(bytes), "application/octet-stream"),
            ),
          )
          .pipe(Effect.mapError(unavailable));

        const body = yield* response.json.pipe(Effect.mapError(unavailable));

        if (response.status >= 400) {
          const refusal = yield* Schema.decodeUnknownEffect(Refusal)(body).pipe(
            Effect.orElseSucceed(() => ({ reason: "The drawing did not upload." })),
          );

          return yield* new DeskFailed(refusal);
        }

        return yield* Schema.decodeUnknownEffect(Uploaded)(body).pipe(Effect.mapError(unavailable));
      }),
    };
  }),
).pipe(Layer.provide(FetchHttpClient.layer));

const runtime = Atom.runtime(DeskClientLive);

export const deskFlow = createActorAtoms(runtime, deskFlowMachine);
