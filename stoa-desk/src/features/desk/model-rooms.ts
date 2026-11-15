import type { ModelElement, ModelMesh } from "./model-payload.ts";

export interface Room {
  readonly area: number;
  readonly element: number;
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface Plates {
  readonly mesh: ModelMesh;
  readonly rooms: readonly Room[];
}

const plateLift = 0.02;

const floorBand = 0.03;

const lowest = (source: ModelMesh, first: number, count: number) => {
  let low = Number.POSITIVE_INFINITY;

  for (let corner = first * 3; corner < (first + count) * 3; corner += 1) {
    low = Math.min(low, source.positions[(source.indices[corner] ?? 0) * 3 + 1] ?? 0);
  }

  return low;
};

const floorTriangle = (source: ModelMesh, triangle: number, low: number) => {
  const { indices, positions } = source;
  const corners = [0, 1, 2].map((corner) => indices[triangle * 3 + corner] ?? 0);
  const xs = corners.map((vertex) => positions[vertex * 3] ?? 0);
  const ys = corners.map((vertex) => positions[vertex * 3 + 1] ?? 0);
  const zs = corners.map((vertex) => positions[vertex * 3 + 2] ?? 0);
  const [ax = 0, bx = 0, cx = 0] = xs;
  const [az = 0, bz = 0, cz = 0] = zs;
  const area = Math.abs((bx - ax) * (cz - az) - (cx - ax) * (bz - az)) / 2;

  if (Math.max(...ys) > low + floorBand || area <= 1e-6) {
    return null;
  }

  return { area, corners, x: (ax + bx + cx) / 3, z: (az + bz + cz) / 3 };
};

export const floorPlates = (source: ModelMesh): Plates => {
  const { positions, spans } = source;
  const kept: number[] = [];
  const nextSpans: number[] = [];
  const rooms: Room[] = [];

  for (let span = 0; span < spans.length; span += 3) {
    const element = spans[span] ?? 0;
    const first = spans[span + 1] ?? 0;
    const count = spans[span + 2] ?? 0;
    const low = lowest(source, first, count);
    const start = kept.length / 3;
    let area = 0;
    let sumX = 0;
    let sumZ = 0;

    for (let triangle = first; triangle < first + count; triangle += 1) {
      const floor = floorTriangle(source, triangle, low);

      if (floor !== null) {
        kept.push(...floor.corners);
        area += floor.area;
        sumX += floor.area * floor.x;
        sumZ += floor.area * floor.z;
      }
    }

    const triangles = kept.length / 3 - start;

    if (triangles > 0) {
      nextSpans.push(element, start, triangles);
      rooms.push({ area, element, x: sumX / area, y: low + plateLift, z: sumZ / area });
    }
  }

  const lifted = Float32Array.from(positions);

  for (let index = 1; index < lifted.length; index += 3) {
    lifted[index] = (lifted[index] ?? 0) + plateLift;
  }

  return {
    mesh: {
      group: source.group,
      indices: Uint32Array.from(kept),
      positions: lifted,
      spans: Uint32Array.from(nextSpans),
      storey: source.storey,
    },
    rooms,
  };
};

export const roomText = (element: ModelElement | undefined, area: number | undefined) => {
  const name = element === undefined ? "" : element.name || element.long;
  const known = element?.area ?? area ?? 0;
  const size = known > 0 ? `${known.toFixed(1)} m²` : "";

  return [name === "" ? "Room" : name, size].filter((part) => part !== "").join(" · ");
};

export const matchesRoom = (element: ModelElement, wanted: readonly string[]) => {
  const names = [element.name, element.long, `${element.name} ${element.long}`].map((name) =>
    name.trim().toLowerCase(),
  );

  return wanted.some((want) => {
    const key = want.trim().toLowerCase();

    return key !== "" && names.includes(key);
  });
};
