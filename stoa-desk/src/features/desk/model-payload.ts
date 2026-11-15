import { Schema } from "effect";

const Slice = Schema.Struct({ length: Schema.Finite, offset: Schema.Finite });

export const ModelGroup = Schema.Literals([
  "beam",
  "column",
  "door",
  "furniture",
  "glass",
  "other",
  "roof",
  "slab",
  "space",
  "stair",
  "wall",
  "window",
]);

export type ModelGroup = typeof ModelGroup.Type;

const Header = Schema.Struct({
  elements: Schema.Array(
    Schema.Struct({
      area: Schema.optional(Schema.Finite),
      group: ModelGroup,
      id: Schema.Finite,
      label: Schema.String,
      long: Schema.optional(Schema.String),
      name: Schema.optional(Schema.String),
      storey: Schema.Finite,
    }),
  ),
  meshes: Schema.Array(
    Schema.Struct({
      group: ModelGroup,
      indices: Slice,
      positions: Slice,
      spans: Slice,
      storey: Schema.Finite,
    }),
  ),
  size: Schema.Array(Schema.Finite),
  storeys: Schema.Array(Schema.Struct({ elevation: Schema.Finite, name: Schema.String })),
});

export interface ModelMesh {
  readonly group: ModelGroup;
  readonly indices: Uint32Array;
  readonly positions: Float32Array;
  readonly spans: Uint32Array;
  readonly storey: number;
}

export interface ModelStorey {
  readonly elevation: number;
  readonly name: string;
}

export interface ModelElement {
  readonly area: number | null;
  readonly group: ModelGroup;
  readonly label: string;
  readonly long: string;
  readonly name: string;
  readonly storey: number;
}

export interface BuildingModel {
  readonly elements: readonly ModelElement[];
  readonly meshes: readonly ModelMesh[];
  readonly storeys: readonly ModelStorey[];
}

export const readModel = (buffer: ArrayBuffer): BuildingModel => {
  const length = new DataView(buffer).getUint32(0, true);
  const text = new TextDecoder().decode(new Uint8Array(buffer, 4, length));
  const header = Schema.decodeUnknownSync(Header)(JSON.parse(text));
  const start = 4 + length;

  return {
    elements: header.elements.map((element) => ({
      area: element.area ?? null,
      group: element.group,
      label: element.label,
      long: element.long ?? "",
      name: element.name ?? "",
      storey: element.storey,
    })),
    meshes: header.meshes.map((mesh) => ({
      group: mesh.group,
      indices: new Uint32Array(buffer, start + mesh.indices.offset, mesh.indices.length),
      positions: new Float32Array(buffer, start + mesh.positions.offset, mesh.positions.length),
      spans: new Uint32Array(buffer, start + mesh.spans.offset, mesh.spans.length),
      storey: mesh.storey,
    })),
    storeys: header.storeys,
  };
};
