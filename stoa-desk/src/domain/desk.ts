import { Schema } from "effect";

export const FactStatus = Schema.Literals(["known", "estimated", "unknown"]);

export type FactStatus = typeof FactStatus.Type;

export const Fact = Schema.Struct({
  basis: Schema.optionalKey(Schema.String),
  confidence: Schema.optionalKey(Schema.Finite),
  key: Schema.String,
  margin: Schema.optionalKey(Schema.String),
  marginBasis: Schema.optionalKey(Schema.String),
  note: Schema.String,
  source: Schema.String,
  status: FactStatus,
  unit: Schema.String,
  value: Schema.NullOr(Schema.String),
});

export type Fact = typeof Fact.Type;

const Point = Schema.Array(Schema.Finite);

export const Geometry = Schema.Literals(["point", "box", "line", "polygon"]);

export type Geometry = typeof Geometry.Type;

export const Entity = Schema.Struct({
  facts: Schema.Array(Fact),
  group: Schema.String,
  id: Schema.String,
  kind: Schema.String,
  label: Schema.String,
  members: Schema.optionalKey(Schema.Array(Schema.String)),
  page: Schema.Finite,
  points: Schema.Array(Point),
  geometry: Geometry,
  warnings: Schema.optionalKey(Schema.Array(Schema.String)),
});

export type Entity = typeof Entity.Type;

export const Page = Schema.Struct({
  height: Schema.Finite,
  index: Schema.Finite,
  unit: Schema.String,
  width: Schema.Finite,
});

export type Page = typeof Page.Type;

export const PageLayer = Schema.Literals(["page", "ink", "walls"]);

export type PageLayer = typeof PageLayer.Type;

export const Method = Schema.Literals(["deterministic", "model"]);

export type Method = typeof Method.Type;

export const Tool = Schema.Struct({
  description: Schema.String,
  method: Method,
  name: Schema.String,
  title: Schema.String,
});

export const Conflict = Schema.Struct({
  entityIds: Schema.Array(Schema.String),
  id: Schema.String,
  text: Schema.String,
});

export type Conflict = typeof Conflict.Type;

export const DrawingDocument = Schema.Struct({
  conflicts: Schema.Array(Conflict),
  entities: Schema.Array(Entity),
  id: Schema.String,
  ingestMs: Schema.Finite,
  kind: Schema.String,
  kindLabel: Schema.String,
  name: Schema.String,
  pages: Schema.Array(Page),
  questions: Schema.Array(Schema.String),
  samples: Schema.Array(
    Schema.Struct({
      format: Schema.String,
      id: Schema.String,
      name: Schema.String,
      tag: Schema.String,
    }),
  ),
  summary: Schema.Array(Fact),
  tools: Schema.Array(Tool),
  unknown: Schema.Array(Schema.String),
});

export type DrawingDocument = typeof DrawingDocument.Type;

export const EvidenceMark = Schema.Struct({
  id: Schema.String,
  kind: Schema.String,
  note: Schema.String,
  page: Schema.Finite,
  points: Schema.Array(Point),
  ref: Schema.String,
  geometry: Geometry,
});

export type EvidenceMark = typeof EvidenceMark.Type;

export const Step = Schema.Struct({
  argumentsJson: Schema.String,
  dataJson: Schema.String,
  done: Schema.Boolean,
  entityIds: Schema.Array(Schema.String),
  error: Schema.String,
  id: Schema.String,
  kind: Schema.Literals(["tool", "calc", "final"]),
  method: Method,
  ms: Schema.NullOr(Schema.Finite),
  ok: Schema.Boolean,
  rowLinks: Schema.Array(
    Schema.Struct({ entityIds: Schema.Array(Schema.String), path: Schema.String }),
  ),
  marks: Schema.Array(EvidenceMark),
  sentence: Schema.String,
  skipped: Schema.Boolean,
  thought: Schema.String,
  title: Schema.String,
  tool: Schema.String,
});

export type Step = typeof Step.Type;

const AnswerValue = Schema.Union([Schema.String, Schema.Finite]);

const sourceFields = {
  entityIds: Schema.Array(Schema.String),
  key: Schema.String,
  label: Schema.String,
  path: Schema.String,
  places: Schema.Finite,
  stepId: Schema.NullOr(Schema.String),
  tool: Schema.String,
  value: AnswerValue,
  warnings: Schema.Array(Schema.String),
};

export const Operand = Schema.Struct({ ...sourceFields, operands: Schema.Array(Schema.Never) });

export type Operand = typeof Operand.Type;

export const Derivation = Schema.Struct({ ...sourceFields, operands: Schema.Array(Operand) });

export type Derivation = typeof Derivation.Type;

export const CheckState = Schema.Literals(["pass", "warn", "fail"]);

export type CheckState = typeof CheckState.Type;

export const Check = Schema.Struct({
  detail: Schema.String,
  factor: Schema.Finite,
  id: Schema.String,
  label: Schema.String,
  state: CheckState,
  stepId: Schema.NullOr(Schema.String),
});

export type Check = typeof Check.Type;

export const Confidence = Schema.Struct({
  basis: Schema.String,
  checks: Schema.Array(Check),
  level: Schema.Literals(["high", "medium", "low", "none"]),
  modelClaim: Schema.NullOr(Schema.Finite),
  score: Schema.NullOr(Schema.Finite),
});

export type Confidence = typeof Confidence.Type;

export const Answer = Schema.Struct({
  abstain: Schema.NullOr(
    Schema.Struct({ detail: Schema.String, reason: Schema.String, request: Schema.String }),
  ),
  bestEstimate: Schema.NullOr(AnswerValue),
  confidence: Confidence,
  convention: Schema.String,
  costUsd: Schema.Finite,
  derivation: Schema.NullOr(Derivation),
  margin: Schema.NullOr(
    Schema.Struct({
      basis: Schema.String,
      percent: Schema.Finite,
      plus: Schema.Finite,
      text: Schema.String,
    }),
  ),
  rejections: Schema.Finite,
  status: Schema.Literals(["answered", "abstained", "error"]),
  unit: Schema.NullOr(Schema.String),
  value: Schema.NullOr(AnswerValue),
});

export type Answer = typeof Answer.Type;

export const RunStatus = Schema.Literals(["running", "answered", "abstained", "error"]);

export const Run = Schema.Struct({
  about: Schema.Array(Schema.String),
  activity: Schema.String,
  answer: Schema.NullOr(Answer),
  documentId: Schema.String,
  elapsedMs: Schema.Finite,
  error: Schema.String,
  id: Schema.String,
  question: Schema.String,
  status: RunStatus,
  steps: Schema.Array(Step),
});

export type Run = typeof Run.Type;

const Id = Schema.String.check(Schema.isMinLength(1), Schema.isMaxLength(80));

export const OpenRequest = Schema.Struct({ sample: Id });

export type OpenRequest = typeof OpenRequest.Type;

export const AskRequest = Schema.Struct({
  about: Schema.Array(Id).check(Schema.isMaxLength(60)),
  documentId: Id,
  question: Schema.String.check(Schema.isMinLength(1), Schema.isMaxLength(500)),
});

export type AskRequest = typeof AskRequest.Type;

export const Language = Schema.Literals([
  "English",
  "Finnish",
  "Swedish",
  "German",
  "French",
  "Spanish",
  "Norwegian",
  "Romanian",
]);

export type Language = typeof Language.Type;

export const TranslateRequest = Schema.Struct({ documentId: Id, language: Language });

export type TranslateRequest = typeof TranslateRequest.Type;

export const Translation = Schema.Struct({
  language: Language,
  texts: Schema.Record(Schema.String, Schema.String),
});

export type Translation = typeof Translation.Type;

export const SamplePart = Schema.Literals(["file", "thumb", "stage"]);

export type SamplePart = typeof SamplePart.Type;

export const Uploaded = Schema.Struct({ sample: Id });

export type Uploaded = typeof Uploaded.Type;

export const ScaleRequest = Schema.Struct({
  documentId: Id,
  lengthM: Schema.Finite.check(Schema.isGreaterThan(0)),
  points: Schema.Tuple([
    Schema.Tuple([Schema.Finite, Schema.Finite]),
    Schema.Tuple([Schema.Finite, Schema.Finite]),
  ]),
});

export type ScaleRequest = typeof ScaleRequest.Type;

export const Scaled = Schema.Struct({
  conflicts: Schema.Array(Conflict),
  entities: Schema.Array(Entity),
  kind: Schema.String,
  kindLabel: Schema.String,
  pages: Schema.Array(Page),
  summary: Schema.Array(Fact),
  tools: Schema.Array(Tool),
  unknown: Schema.Array(Schema.String),
});

export type Scaled = typeof Scaled.Type;

export const RemoveRequest = Schema.Struct({ sample: Id });

export type RemoveRequest = typeof RemoveRequest.Type;

export const Removed = Schema.Struct({
  samples: Schema.Array(Schema.Struct({ id: Schema.String })),
});

export type Removed = typeof Removed.Type;

export const UploadRequest = Schema.Struct({ file: Schema.File });

export type UploadRequest = typeof UploadRequest.Type;

export const PollRequest = Schema.Struct({ runId: Id });

export type PollRequest = typeof PollRequest.Type;

export class DeskFailed extends Schema.TaggedError<DeskFailed>()("DeskFailed", {
  reason: Schema.String,
}) {}
