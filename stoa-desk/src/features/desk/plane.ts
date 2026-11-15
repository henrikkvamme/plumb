export type Point = readonly [number, number];

export type Matrix = readonly [
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
  number,
];

const width = 9;

const eliminate = (cells: number[]): boolean => {
  const cell = (row: number, column: number) => cells[row * width + column] ?? 0;

  const swap = (a: number, b: number) => {
    for (let column = 0; column < width; column += 1) {
      const kept = cell(a, column);

      cells[a * width + column] = cell(b, column);
      cells[b * width + column] = kept;
    }
  };

  for (let column = 0; column < 8; column += 1) {
    let best = column;

    for (let row = column + 1; row < 8; row += 1) {
      if (Math.abs(cell(row, column)) > Math.abs(cell(best, column))) {
        best = row;
      }
    }

    if (Math.abs(cell(best, column)) < 1e-10) {
      return false;
    }

    swap(column, best);

    const pivot = cell(column, column);

    for (let row = 0; row < 8; row += 1) {
      const factor = row === column ? 0 : cell(row, column) / pivot;

      if (factor !== 0) {
        for (let at = column; at < width; at += 1) {
          cells[row * width + at] = cell(row, at) - factor * cell(column, at);
        }
      }
    }
  }

  return true;
};

export const solve = (from: readonly Point[], to: readonly Point[]): Matrix | null => {
  if (from.length < 4 || to.length < 4) {
    return null;
  }

  const cells: number[] = [];

  for (let index = 0; index < 4; index += 1) {
    const [x, y] = from[index] ?? [0, 0];
    const [u, v] = to[index] ?? [0, 0];

    cells.push(x, y, 1, 0, 0, 0, -u * x, -u * y, u, 0, 0, 0, x, y, 1, -v * x, -v * y, v);
  }

  if (!eliminate(cells)) {
    return null;
  }

  const cell = (row: number, column: number) => cells[row * width + column] ?? 0;
  const h = Array.from({ length: 8 }, (_, index) => cell(index, 8) / cell(index, index));

  if (h.some((value) => !Number.isFinite(value))) {
    return null;
  }

  const [a = 0, b = 0, c = 0, d = 0, e = 0, f = 0, g = 0, k = 0] = h;

  return [a, b, c, d, e, f, g, k, 1];
};

export const invert = (m: Matrix): Matrix | null => {
  const [a, b, c, d, e, f, g, h, i] = m;
  const det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g);

  if (Math.abs(det) < 1e-14) {
    return null;
  }

  return [
    (e * i - f * h) / det,
    (c * h - b * i) / det,
    (b * f - c * e) / det,
    (f * g - d * i) / det,
    (a * i - c * g) / det,
    (c * d - a * f) / det,
    (d * h - e * g) / det,
    (b * g - a * h) / det,
    (a * e - b * d) / det,
  ];
};

export const apply = (m: Matrix, point: Point): Point => {
  const [x, y] = point;
  const w = m[6] * x + m[7] * y + m[8];

  return [(m[0] * x + m[1] * y + m[2]) / w, (m[3] * x + m[4] * y + m[5]) / w];
};

export const inside = (ring: readonly Point[], point: Point): boolean => {
  const [px, py] = point;
  let hit = false;

  for (const [index, a] of ring.entries()) {
    const b = ring[(index + ring.length - 1) % ring.length] ?? a;
    const crosses = a[1] > py !== b[1] > py;

    if (crosses && px < ((b[0] - a[0]) * (py - a[1])) / (b[1] - a[1]) + a[0]) {
      hit = !hit;
    }
  }

  return hit;
};

export const segmentDistance = (point: Point, a: Point, b: Point): number => {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const length = dx * dx + dy * dy;

  const share =
    length === 0
      ? 0
      : Math.min(1, Math.max(0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length));

  return Math.hypot(point[0] - (a[0] + dx * share), point[1] - (a[1] + dy * share));
};

export const pointOf = (point: readonly number[]): Point => [point[0] ?? 0, point[1] ?? 0];
