import { Option, Predicate, Schema } from "effect";

const units = new Map([
  ["ft2", "ft²"],
  ["m2", "m²"],
  ["m3", "m³"],
  ["sqft", "ft²"],
]);

export const unitLabel = (unit: string | null): string =>
  unit === null ? "" : (units.get(unit) ?? unit);

export const numberLabel = (value: number): string => {
  if (Number.isInteger(value)) {
    return String(value);
  }

  const scale = Math.abs(value) < 1 ? 10_000 : 100;

  return String(Math.round(value * scale) / scale);
};

export const valueLabel = (value: string | number | null): string => {
  if (value === null) {
    return "";
  }

  return Predicate.isNumber(value) ? numberLabel(value) : value;
};

export const percentLabel = (share: number): string => `${(share * 100).toFixed(1)}%`;

export const secondsLabel = (ms: number): string => `${(ms / 1000).toFixed(1)} s`;

const JsonText = Schema.fromJsonString(Schema.Json);

export const parseJson = (text: string): Schema.Json | undefined =>
  text === "" ? undefined : Option.getOrUndefined(Schema.decodeOption(JsonText)(text));

type JsonObject = Readonly<Record<string, Schema.Json>>;

export const isJsonObject = (value: Schema.Json | undefined): value is JsonObject =>
  Predicate.isObject(value) && !Array.isArray(value);
