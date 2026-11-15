import type { Geometry } from "#/domain/desk.ts";

import { boundsOf } from "./geometry.ts";
import type { Points } from "./geometry.ts";
import { pointOf } from "./plane.ts";
import type { Point } from "./plane.ts";

export type Rgb = readonly [number, number, number];

export interface SheetLook {
  readonly ink: Rgb;
  readonly inkUrl: string;
  readonly pageHeight: number;
  readonly pageWidth: number;
  readonly paper: Rgb;
  readonly screen: number;
  readonly sheetW: number;
  readonly wallsUrl: string;
}

export interface Figure {
  readonly fillAlpha: number;
  readonly geometry: Geometry;
  readonly lineAlpha: number;
  readonly lineWidth: number;
  readonly points: Points;
  readonly tone: Rgb;
}

export interface SheetPainter {
  readonly draw: (tilt: number, turn: number) => void;
  readonly setLook: (look: SheetLook) => Promise<void>;
  readonly setMarks: (figures: readonly Figure[], key: string) => void;
}

interface Layers {
  readonly base: HTMLCanvasElement;
  readonly look: SheetLook;
  readonly q: number;
  readonly side: HTMLCanvasElement;
  readonly top: HTMLCanvasElement;
}

interface PainterState {
  drawn: string;
  figures: readonly Figure[];
  layers: Layers | null;
  marksKey: string;
  version: number;
}

const backingLimit = 4096;

const wallScale = 0.75;

const wallFade = 0.62;

const capFade = 0.86;

const wallFullAt = Math.tan((24 * Math.PI) / 180);

const inkAlpha = 0.85;

const shadowAlpha = 0.28;

const images = new Map<string, Promise<HTMLImageElement | null>>();

const load = (url: string): Promise<HTMLImageElement | null> => {
  const cached = images.get(url);

  if (cached !== undefined) {
    return cached;
  }

  const image = new Image();

  image.decoding = "async";
  image.src = url;

  const pending = image
    .decode()
    .then((): HTMLImageElement | null => image)
    .catch(() => {
      images.delete(url);

      return null;
    });

  images.set(url, pending);

  const [oldest] = images.keys();

  if (images.size > 6 && oldest !== undefined) {
    images.delete(oldest);
  }

  return pending;
};

const rgba = (colour: Rgb, alpha: number) =>
  `rgba(${String(colour[0])}, ${String(colour[1])}, ${String(colour[2])}, ${String(alpha)})`;

const mix = (a: Rgb, b: Rgb, share: number): Rgb => [
  Math.round(a[0] + (b[0] - a[0]) * share),
  Math.round(a[1] + (b[1] - a[1]) * share),
  Math.round(a[2] + (b[2] - a[2]) * share),
];

const make = (width: number, height: number) => {
  const canvas = document.createElement("canvas");

  canvas.width = Math.max(1, Math.round(width));
  canvas.height = Math.max(1, Math.round(height));

  return canvas;
};

const release = (canvas: HTMLCanvasElement | null) => {
  if (canvas !== null) {
    canvas.width = 0;
    canvas.height = 0;
  }
};

export const resolveColour = (value: string, fallback: Rgb): Rgb => {
  const text = value.trim();

  if (text === "") {
    return fallback;
  }

  const context = make(1, 1).getContext("2d", { willReadFrequently: true });

  if (context === null) {
    return fallback;
  }

  const sentinel = "#010203";

  context.fillStyle = sentinel;
  context.fillStyle = text;

  if (context.fillStyle === sentinel) {
    return fallback;
  }

  context.fillRect(0, 0, 1, 1);

  const [r = fallback[0], g = fallback[1], b = fallback[2]] = context.getImageData(0, 0, 1, 1).data;

  return [r, g, b];
};

const tinted = (
  image: HTMLImageElement,
  colour: Rgb,
  size: Point,
  box: readonly [number, number, number, number],
) => {
  const canvas = make(size[0], size[1]);
  const context = canvas.getContext("2d");

  if (context === null) {
    return canvas;
  }

  context.drawImage(image, box[0], box[1], box[2], box[3]);
  context.globalCompositeOperation = "source-in";
  context.fillStyle = rgba(colour, 1);
  context.fillRect(0, 0, canvas.width, canvas.height);

  return canvas;
};

const capped = (
  look: SheetLook,
  ink: HTMLImageElement,
  walls: HTMLImageElement,
  size: Point,
  box: readonly [number, number, number, number],
) => {
  const top = tinted(walls, mix(look.ink, look.paper, capFade), size, box);
  const context = top.getContext("2d");

  if (context === null) {
    return top;
  }

  const lines = tinted(ink, look.ink, size, box);

  context.globalCompositeOperation = "source-atop";
  context.drawImage(lines, 0, 0);
  release(lines);

  return top;
};

export const sheetPad = (sheetW: number): number => Math.round(sheetW * 0.08);

export const wallTopOf = (sheetW: number): number => sheetW * 0.0092;

const trace = (context: CanvasRenderingContext2D, figure: Figure, layers: Layers) => {
  const { look, q } = layers;
  const pad = sheetPad(look.sheetW) * q;
  const scale = (look.sheetW / look.pageWidth) * q;
  const unit = q * look.screen;

  const at = (point: readonly number[]): Point => {
    const [x, y] = pointOf(point);

    return [pad + x * scale, pad + y * scale];
  };

  const box = boundsOf(figure.points);

  context.beginPath();

  if (box === null) {
    return;
  }

  if (figure.geometry === "polygon") {
    for (const [index, point] of figure.points.entries()) {
      const [x, y] = at(point);

      if (index === 0) {
        context.moveTo(x, y);
      } else {
        context.lineTo(x, y);
      }
    }

    context.closePath();

    return;
  }

  if (figure.geometry === "box") {
    const [x0, y0] = at([box.x0, box.y0]);
    const [x1, y1] = at([box.x1, box.y1]);
    const edge = 3 * unit;

    context.roundRect(x0 - edge, y0 - edge, x1 - x0 + 2 * edge, y1 - y0 + 2 * edge, edge);

    return;
  }

  if (figure.geometry === "line") {
    const [first = [box.x0, box.y0], second = [box.x1, box.y1]] = figure.points;
    const [x0, y0] = at(first);
    const [x1, y1] = at(second);

    context.moveTo(x0, y0);
    context.lineTo(x1, y1);

    return;
  }

  const [x, y] = at([box.x0, box.y0]);

  context.arc(x, y, 9 * unit, 0, Math.PI * 2);
};

const fillFigures = (
  context: CanvasRenderingContext2D,
  figures: readonly Figure[],
  layers: Layers,
) => {
  for (const figure of figures) {
    if (figure.geometry !== "line" && figure.fillAlpha > 0) {
      trace(context, figure, layers);
      context.fillStyle = rgba(figure.tone, figure.fillAlpha);
      context.fill();
    }
  }
};

const strokeFigures = (
  context: CanvasRenderingContext2D,
  figures: readonly Figure[],
  layers: Layers,
) => {
  const unit = layers.q * layers.look.screen;

  context.setLineDash([]);
  context.lineJoin = "round";
  context.lineCap = "round";

  for (const figure of figures) {
    const width = figure.geometry === "line" ? figure.lineWidth + 1.6 : figure.lineWidth;

    if (width > 0 && figure.lineAlpha > 0) {
      trace(context, figure, layers);
      context.strokeStyle = rgba(figure.tone, figure.lineAlpha);
      context.lineWidth = width * unit;
      context.stroke();
    }
  }
};

const build = (look: SheetLook, ink: HTMLImageElement, walls: HTMLImageElement): Layers | null => {
  const sheetH = (look.sheetW * look.pageHeight) / look.pageWidth;
  const pad = sheetPad(look.sheetW);
  const cssW = look.sheetW + 2 * pad;
  const cssH = sheetH + 2 * pad;
  const ratio = window.devicePixelRatio > 0 ? window.devicePixelRatio : 1;
  const q = Math.min(ratio, backingLimit / cssW, backingLimit / cssH);
  const size: Point = [Math.round(cssW * q), Math.round(cssH * q)];
  const box = [pad * q, pad * q, look.sheetW * q, sheetH * q] as const;
  const base = make(size[0], size[1]);
  const context = base.getContext("2d");

  if (context === null) {
    return null;
  }

  const reach = (10 * look.sheetW) / 1100;
  const angle = (135 * Math.PI) / 180;
  const shade = tinted(walls, [0, 0, 0], size, box);

  context.save();
  context.globalAlpha = shadowAlpha;
  context.filter = `blur(${((7 * look.sheetW * q) / 1100).toFixed(2)}px)`;
  context.drawImage(shade, Math.cos(angle) * reach * q, Math.sin(angle) * reach * q);
  context.restore();
  release(shade);

  const lines = tinted(ink, look.ink, size, box);

  context.save();
  context.globalAlpha = inkAlpha;
  context.drawImage(lines, 0, 0);
  context.restore();
  release(lines);

  const small: Point = [size[0] * wallScale, size[1] * wallScale];

  const smallBox = [
    box[0] * wallScale,
    box[1] * wallScale,
    box[2] * wallScale,
    box[3] * wallScale,
  ] as const;

  return {
    base,
    look,
    q,
    side: tinted(walls, mix(look.ink, look.paper, wallFade), small, smallBox),
    top: capped(look, ink, walls, small, smallBox),
  };
};

export const createSheetPainter = (canvas: HTMLCanvasElement): SheetPainter => {
  const state: PainterState = { drawn: "", figures: [], layers: null, marksKey: "", version: 0 };

  const setLook = async (look: SheetLook) => {
    state.version += 1;

    const { version } = state;
    const [ink, walls] = await Promise.all([load(look.inkUrl), load(look.wallsUrl)]);

    if (version !== state.version || ink === null || walls === null) {
      return;
    }

    const layers = build(look, ink, walls);

    if (layers === null) {
      return;
    }

    const old = state.layers;

    state.layers = layers;
    state.drawn = "";

    if (old !== null) {
      release(old.base);
      release(old.side);
      release(old.top);
    }

    if (canvas.width !== layers.base.width || canvas.height !== layers.base.height) {
      canvas.width = layers.base.width;
      canvas.height = layers.base.height;
    }
  };

  const setMarks = (figures: readonly Figure[], key: string) => {
    if (key === state.marksKey) {
      return;
    }

    state.marksKey = key;
    state.figures = figures;
    state.drawn = "";
  };

  const draw = (tilt: number, turn: number) => {
    const { figures, layers } = state;

    if (layers === null) {
      return;
    }

    const { base, look, q, side, top } = layers;
    const radians = Math.PI / 180;
    const lift = wallTopOf(look.sheetW) * q;
    const limit = Math.tan(72 * radians);
    const rise = -lift * Math.max(-limit, Math.min(limit, Math.tan(tilt * radians)));
    const ex = rise * Math.sin(turn * radians);
    const ey = rise * Math.cos(turn * radians);
    const key = `${String(Math.round(ex * 3))},${String(Math.round(ey * 3))}`;

    if (key === state.drawn) {
      return;
    }

    const context = canvas.getContext("2d");

    if (context === null) {
      return;
    }

    state.drawn = key;

    const { height, width } = canvas;

    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, width, height);
    context.drawImage(base, 0, 0);
    fillFigures(context, figures, layers);

    const raised = Math.min(1, Math.hypot(ex, ey) / (lift * wallFullAt));

    if (raised > 0) {
      const steps = Math.max(1, Math.min(14, Math.ceil(Math.hypot(ex, ey) / 1.4)));

      context.imageSmoothingEnabled = true;
      context.globalAlpha = raised;

      for (let step = 0; step < steps; step += 1) {
        const share = step / steps;

        context.drawImage(side, ex * share, ey * share, width, height);
      }

      context.drawImage(top, ex, ey, width, height);
      context.globalAlpha = 1;
    }

    context.translate(ex, ey);
    strokeFigures(context, figures, layers);
    context.setTransform(1, 0, 0, 1, 0, 0);
  };

  return { draw, setLook, setMarks };
};
