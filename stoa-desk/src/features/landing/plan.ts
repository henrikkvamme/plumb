export type FactStatus = "known" | "estimated" | "unknown";

type Point = readonly [number, number];

export interface Room {
  readonly across: readonly [number, number, number];
  readonly down: readonly [number, number, number];
  readonly label: Point;
  readonly name: string;
  readonly outline: readonly Point[];
  readonly status: FactStatus;
}

const unitsPerMetre = 20;

export const planWidth = 320;

export const planHeight = 220;

export const wallPath =
  "M20 20H300V200H20Z M20 96H132 M132 20V132 M132 132H196 M196 96V200 M196 96H300 M236 20V96 M84 96V200";

export const rooms: readonly Room[] = [
  {
    across: [26, 126, 36],
    down: [31, 46, 90],
    label: [80, 66],
    name: "Bedroom 1",
    outline: [
      [20, 20],
      [132, 20],
      [132, 96],
      [20, 96],
    ],
    status: "known",
  },
  {
    across: [138, 230, 36],
    down: [143, 46, 126],
    label: [188, 72],
    name: "Living room",
    outline: [
      [132, 20],
      [236, 20],
      [236, 96],
      [196, 96],
      [196, 132],
      [132, 132],
    ],
    status: "known",
  },
  {
    across: [242, 294, 36],
    down: [247, 46, 90],
    label: [272, 66],
    name: "Kitchen",
    outline: [
      [236, 20],
      [300, 20],
      [300, 96],
      [236, 96],
    ],
    status: "known",
  },
  {
    across: [202, 294, 112],
    down: [207, 122, 194],
    label: [254, 156],
    name: "Bedroom 2",
    outline: [
      [196, 96],
      [300, 96],
      [300, 200],
      [196, 200],
    ],
    status: "known",
  },
  {
    across: [90, 190, 188],
    down: [95, 102, 178],
    label: [146, 160],
    name: "Hall",
    outline: [
      [84, 96],
      [132, 96],
      [132, 132],
      [196, 132],
      [196, 200],
      [84, 200],
    ],
    status: "known",
  },
  {
    across: [26, 78, 112],
    down: [31, 122, 194],
    label: [54, 156],
    name: "Bath",
    outline: [
      [20, 96],
      [84, 96],
      [84, 200],
      [20, 200],
    ],
    status: "estimated",
  },
];

export const pointsOf = (room: Room): string => room.outline.map(([x, y]) => `${x},${y}`).join(" ");

export const clipOf = (room: Room): string =>
  `polygon(${room.outline
    .map(([x, y]) => `${(x / planWidth) * 100}% ${(y / planHeight) * 100}%`)
    .join(", ")})`;

const edgesOf = (room: Room): readonly (readonly [Point, Point])[] =>
  room.outline.map((point, index) => [
    point,
    room.outline[(index + 1) % room.outline.length] ?? point,
  ]);

export const areaOf = (room: Room): number => {
  let twice = 0;

  for (const [[x, y], [nextX, nextY]] of edgesOf(room)) {
    twice += x * nextY - nextX * y;
  }

  return Math.abs(twice) / 2 / unitsPerMetre ** 2;
};

export const perimeterOf = (room: Room): number => {
  let length = 0;

  for (const [[x, y], [nextX, nextY]] of edgesOf(room)) {
    length += Math.hypot(nextX - x, nextY - y);
  }

  return length / unitsPerMetre;
};

export const sizeOf = (room: Room): readonly [number, number] => {
  const xs = room.outline.map(([x]) => x);
  const ys = room.outline.map(([, y]) => y);

  return [
    (Math.max(...xs) - Math.min(...xs)) / unitsPerMetre,
    (Math.max(...ys) - Math.min(...ys)) / unitsPerMetre,
  ];
};

export const metres = (value: number): string => `${value.toFixed(1)} m`;

export const squareMetres = (value: number): string => `${value.toFixed(1)} m²`;

export const planMetres = (share: number, extent: number): string =>
  ((share * extent) / unitsPerMetre).toFixed(2);

export const estimateMargin = 0.6;

const areas = rooms.map(areaOf);

export const largestArea = Math.max(...areas);

const sumOf = (values: readonly number[]): number => {
  let sum = 0;

  for (const value of values) {
    sum += value;
  }

  return sum;
};

const totalArea = sumOf(areas);

const largestIndex = areas.indexOf(largestArea);

const largest = rooms[largestIndex];

const largestSize = largest === undefined ? [0, 0] : sizeOf(largest);

export interface Question {
  readonly answer: string;
  readonly checks: readonly string[];
  readonly detail: string;
  readonly id: string;
  readonly measured: number | null;
  readonly rooms: readonly number[];
  readonly status: FactStatus;
  readonly text: string;
}

export const questions: readonly Question[] = [
  {
    answer: largest?.name ?? "",
    checks: [
      "Scale 1:100, from the title block",
      `${rooms.length} rooms measured`,
      `The dimension text agrees: ${(largestSize[0] ?? 0).toFixed(2)} m`,
    ],
    detail: largest === undefined ? "" : squareMetres(areaOf(largest)),
    id: "largest",
    measured: largestIndex,
    rooms: [largestIndex],
    status: "known",
    text: "Which room is the largest?",
  },
  {
    answer: squareMetres(totalArea),
    checks: [
      "Scale 1:100, from the title block",
      `${rooms.length} rooms measured`,
      "The rooms add up to the outline",
    ],
    detail: `± ${estimateMargin.toFixed(1)}, from the bath`,
    id: "total",
    measured: null,
    rooms: rooms.map((_, index) => index),
    status: "estimated",
    text: "What is the total floor area?",
  },
  {
    answer: "Not drawn",
    checks: ["No section drawing in the file", "No height text on the sheet"],
    detail: "A floor plan has no heights",
    id: "height",
    measured: null,
    rooms: [],
    status: "unknown",
    text: "How high is the ceiling?",
  },
];
