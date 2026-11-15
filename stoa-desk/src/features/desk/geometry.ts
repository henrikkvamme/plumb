export type Points = readonly (readonly number[])[];

export interface Box {
  readonly x0: number;
  readonly x1: number;
  readonly y0: number;
  readonly y1: number;
}

export const boundsOf = (points: Points): Box | null => {
  const xs = points.map((point) => point[0] ?? 0);
  const ys = points.map((point) => point[1] ?? 0);

  if (xs.length === 0) {
    return null;
  }

  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
};

export const unionOf = (boxes: readonly (Box | null)[]): Box | null => {
  const real = boxes.filter((box) => box !== null);

  if (real.length === 0) {
    return null;
  }

  return {
    x0: Math.min(...real.map((box) => box.x0)),
    x1: Math.max(...real.map((box) => box.x1)),
    y0: Math.min(...real.map((box) => box.y0)),
    y1: Math.max(...real.map((box) => box.y1)),
  };
};

export const centreOf = (points: Points): readonly [number, number] => {
  const box = boundsOf(points);

  if (box === null) {
    return [0, 0];
  }

  const middle = [(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2] as const;

  if (points.length < 3) {
    return middle;
  }

  const sums = { area: 0, x: 0, y: 0 };

  for (const [index, point] of points.entries()) {
    const next = points[(index + 1) % points.length] ?? point;
    const [x0 = 0, y0 = 0] = point;
    const [x1 = 0, y1 = 0] = next;
    const cross = x0 * y1 - x1 * y0;

    sums.area += cross;
    sums.x += (x0 + x1) * cross;
    sums.y += (y0 + y1) * cross;
  }

  if (Math.abs(sums.area) < 1e-9) {
    return middle;
  }

  return [sums.x / (3 * sums.area), sums.y / (3 * sums.area)];
};

export const pointsAttribute = (points: Points): string =>
  points.map((point) => `${String(point[0] ?? 0)},${String(point[1] ?? 0)}`).join(" ");
