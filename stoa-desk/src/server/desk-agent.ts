import { Config, Context, Effect, Layer, Schema } from "effect";
import { FetchHttpClient, HttpClient, HttpClientRequest } from "effect/http";

import {
  DeskFailed,
  DrawingDocument,
  Removed,
  Run,
  Scaled,
  Translation,
  Uploaded,
} from "#/domain/desk.ts";
import type {
  AskRequest,
  OpenRequest,
  PageLayer,
  PollRequest,
  RemoveRequest,
  SamplePart,
  ScaleRequest,
  TranslateRequest,
} from "#/domain/desk.ts";

const ErrorBody = Schema.Struct({ error: Schema.String });

const unreachable = "The drawing agent does not answer. Start it with `pnpm py` in stoa-desk.";

export class DeskAgent extends Context.Service<
  DeskAgent,
  {
    readonly ask: (request: AskRequest) => Effect.Effect<Run, DeskFailed>;
    readonly model: (documentId: string) => Effect.Effect<ArrayBuffer, DeskFailed>;
    readonly open: (request: OpenRequest) => Effect.Effect<DrawingDocument, DeskFailed>;
    readonly page: (
      documentId: string,
      page: number,
      side: number,
      layer: PageLayer,
    ) => Effect.Effect<ArrayBuffer, DeskFailed>;
    readonly poll: (request: PollRequest) => Effect.Effect<Run, DeskFailed>;
    readonly remove: (request: RemoveRequest) => Effect.Effect<Removed, DeskFailed>;
    readonly sample: (
      id: string,
      part: SamplePart,
    ) => Effect.Effect<
      { readonly bytes: ArrayBuffer; readonly name: string; readonly type: string },
      DeskFailed
    >;
    readonly scale: (request: ScaleRequest) => Effect.Effect<Scaled, DeskFailed>;
    readonly translate: (request: TranslateRequest) => Effect.Effect<Translation, DeskFailed>;
    readonly upload: (name: string, bytes: Uint8Array) => Effect.Effect<Uploaded, DeskFailed>;
  }
>()("stoa-desk/server/desk-agent/DeskAgent") {
  static readonly make = Effect.gen(function* make() {
    const http = yield* HttpClient.HttpClient;
    const port = yield* Config.Int("DESK_PY_PORT").pipe(Config.withDefault(4722), Effect.orDie);
    const base = `http://127.0.0.1:${String(port)}`;

    const send = Effect.fn("DeskAgent.send")(function* send(
      request: HttpClientRequest.HttpClientRequest,
    ) {
      const response = yield* http
        .execute(request)
        .pipe(Effect.mapError(() => new DeskFailed({ reason: unreachable })));

      if (response.status >= 200 && response.status < 300) {
        return response;
      }

      const body = yield* response.json.pipe(Effect.orElseSucceed(() => null));

      const detail = yield* Schema.decodeUnknownEffect(ErrorBody)(body).pipe(
        Effect.orElseSucceed(() => ({ error: `HTTP ${String(response.status)}` })),
      );

      return yield* new DeskFailed({ reason: detail.error });
    });

    const json = <A, I>(schema: Schema.Codec<A, I>, what: string) =>
      Effect.fn("DeskAgent.json")(function* decode(request: HttpClientRequest.HttpClientRequest) {
        const response = yield* send(request);

        const body = yield* response.json.pipe(
          Effect.mapError(() => new DeskFailed({ reason: `The ${what} was not JSON.` })),
        );

        return yield* Schema.decodeUnknownEffect(schema)(body).pipe(
          Effect.mapError(
            (error) =>
              new DeskFailed({
                reason: `The ${what} does not match: ${error.message.slice(0, 300)}`,
              }),
          ),
        );
      });

    const document = json(DrawingDocument, "document");
    const run = json(Run, "run");
    const uploaded = json(Uploaded, "upload");
    const translation = json(Translation, "translation");
    const removed = json(Removed, "list of drawings");
    const scaled = json(Scaled, "drawing with the new scale");

    return {
      ask: Effect.fn("DeskAgent.ask")((request: AskRequest) =>
        run(
          HttpClientRequest.bodyJsonUnsafe(
            HttpClientRequest.post(`${base}/documents/${request.documentId}/ask`),
            { about: request.about, question: request.question },
          ),
        ),
      ),
      model: Effect.fn("DeskAgent.model")(function* model(documentId: string) {
        const response = yield* send(
          HttpClientRequest.get(`${base}/documents/${documentId}/model`),
        );

        const bytes = yield* response.arrayBuffer.pipe(
          Effect.mapError(() => new DeskFailed({ reason: "The 3D model did not arrive." })),
        );

        return bytes;
      }),
      open: Effect.fn("DeskAgent.open")((request: OpenRequest) =>
        document(
          HttpClientRequest.bodyJsonUnsafe(HttpClientRequest.post(`${base}/documents/sample`), {
            sample: request.sample,
          }),
        ),
      ),
      page: Effect.fn("DeskAgent.page")(function* page(
        documentId: string,
        index: number,
        side: number,
        layer: PageLayer,
      ) {
        const response = yield* send(
          HttpClientRequest.get(
            `${base}/documents/${documentId}/pages/${String(index)}?side=${String(side)}&layer=${layer}`,
          ),
        );

        const bytes = yield* response.arrayBuffer.pipe(
          Effect.mapError(() => new DeskFailed({ reason: "The page image did not arrive." })),
        );

        return bytes;
      }),
      poll: Effect.fn("DeskAgent.poll")((request: PollRequest) =>
        run(HttpClientRequest.get(`${base}/runs/${request.runId}`)),
      ),
      sample: Effect.fn("DeskAgent.sample")(function* sample(id: string, part: SamplePart) {
        const response = yield* send(HttpClientRequest.get(`${base}/samples/${id}/${part}`));

        const bytes = yield* response.arrayBuffer.pipe(
          Effect.mapError(() => new DeskFailed({ reason: "The drawing file did not arrive." })),
        );

        return {
          bytes,
          name: response.headers["content-disposition"] ?? "",
          type: response.headers["content-type"] ?? "application/octet-stream",
        };
      }),
      remove: Effect.fn("DeskAgent.remove")((request: RemoveRequest) =>
        removed(HttpClientRequest.delete(`${base}/samples/${request.sample}`)),
      ),
      scale: Effect.fn("DeskAgent.scale")((request: ScaleRequest) =>
        scaled(
          HttpClientRequest.bodyJsonUnsafe(
            HttpClientRequest.post(`${base}/documents/${request.documentId}/scale`),
            { lengthM: request.lengthM, points: request.points },
          ),
        ),
      ),
      translate: Effect.fn("DeskAgent.translate")((request: TranslateRequest) =>
        translation(
          HttpClientRequest.bodyJsonUnsafe(
            HttpClientRequest.post(`${base}/documents/${request.documentId}/translate`),
            { language: request.language },
          ),
        ),
      ),
      upload: Effect.fn("DeskAgent.upload")((name: string, bytes: Uint8Array) =>
        uploaded(
          HttpClientRequest.post(`${base}/documents/upload`).pipe(
            HttpClientRequest.setUrlParam("name", name),
            HttpClientRequest.bodyUint8Array(bytes, "application/octet-stream"),
          ),
        ),
      ),
    };
  });

  static readonly layer = Layer.effect(DeskAgent, DeskAgent.make).pipe(
    Layer.provide(FetchHttpClient.layer),
  );
}
