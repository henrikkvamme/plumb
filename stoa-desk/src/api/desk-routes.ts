import { Option, Schema } from "effect";

import { DeskFailed, PageLayer, SamplePart } from "#/domain/desk.ts";
import { DeskAgent } from "#/server/desk-agent.ts";
import { runApi } from "#/server/runtime.ts";

const sides = { ink: 3000, page: 3000, walls: 1800 } satisfies Record<PageLayer, number>;

const PageQuery = Schema.Struct({
  layer: PageLayer,
  doc: Schema.String.check(Schema.isPattern(/^doc-[0-9a-f]{6,40}$/u)),
  page: Schema.NumberFromString.check(
    Schema.isInt(),
    Schema.isBetween({ maximum: 500, minimum: 0 }),
  ),
});

export const pageImage = async (request: Request): Promise<Response> => {
  const query = Schema.decodeUnknownOption(PageQuery)(
    Object.fromEntries(new URL(request.url).searchParams),
  );

  if (Option.isNone(query)) {
    return Response.json(
      { reason: "Expected ?doc=<id>&page=<number>&layer=<page|ink|walls>." },
      { status: 400 },
    );
  }

  const result = await runApi(DeskFailed)(
    DeskAgent.use((agent) =>
      agent.page(query.value.doc, query.value.page, sides[query.value.layer], query.value.layer),
    ),
  );

  if (!result.ok) {
    return Response.json(result.error, { status: 502 });
  }

  return new Response(result.value, {
    headers: { "Cache-Control": "private, max-age=3600", "Content-Type": "image/png" },
  });
};

const ModelQuery = Schema.Struct({
  doc: Schema.String.check(Schema.isPattern(/^doc-[0-9a-f]{6,40}$/u)),
});

export const modelFile = async (request: Request): Promise<Response> => {
  const query = Schema.decodeUnknownOption(ModelQuery)(
    Object.fromEntries(new URL(request.url).searchParams),
  );

  if (Option.isNone(query)) {
    return Response.json({ reason: "Expected ?doc=<id>." }, { status: 400 });
  }

  const result = await runApi(DeskFailed)(DeskAgent.use((agent) => agent.model(query.value.doc)));

  if (!result.ok) {
    return Response.json(result.error, { status: 404 });
  }

  return new Response(result.value, {
    headers: {
      "Cache-Control": "private, max-age=3600",
      "Content-Type": "application/octet-stream",
    },
  });
};

const sampleId = Schema.String.check(Schema.isPattern(/^[a-z0-9-]{1,60}$/u));

const SampleQuery = Schema.Struct({ id: sampleId, part: SamplePart });

export const sampleFile = async (request: Request): Promise<Response> => {
  const query = Schema.decodeUnknownOption(SampleQuery)(
    Object.fromEntries(new URL(request.url).searchParams),
  );

  if (Option.isNone(query)) {
    return Response.json({ reason: "Expected ?id=<drawing>&part=<file|thumb>." }, { status: 400 });
  }

  const { id, part } = query.value;
  const result = await runApi(DeskFailed)(DeskAgent.use((agent) => agent.sample(id, part)));

  if (!result.ok) {
    return Response.json(result.error, { status: 404 });
  }

  const { bytes, name, type } = result.value;

  const headers = new Headers({
    "Cache-Control": part === "stage" ? "no-store" : "private, max-age=3600",
    "Content-Type": type,
  });

  if (name !== "") {
    headers.set("Content-Disposition", name);
  }

  return new Response(bytes, { headers });
};

const UploadQuery = Schema.Struct({
  name: Schema.String.check(Schema.isMinLength(1), Schema.isMaxLength(200)),
});

const maxUpload = 80_000_000;

export const uploadDrawing = async (request: Request): Promise<Response> => {
  const query = Schema.decodeUnknownOption(UploadQuery)(
    Object.fromEntries(new URL(request.url).searchParams),
  );

  if (Option.isNone(query)) {
    return Response.json({ reason: "The file has no name." }, { status: 400 });
  }

  const bytes = new Uint8Array(await request.arrayBuffer());

  if (bytes.byteLength > maxUpload) {
    return Response.json({ reason: "The file is larger than 80 MB." }, { status: 413 });
  }

  const result = await runApi(DeskFailed)(
    DeskAgent.use((agent) => agent.upload(query.value.name, bytes)),
  );

  return result.ok
    ? Response.json(result.value)
    : Response.json({ reason: result.error.reason }, { status: 422 });
};
