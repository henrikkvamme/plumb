import { Minus, Plus, RotateCcw } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";

import type { Entity, EvidenceMark, Page } from "#/domain/desk.ts";

import { LoadingScene } from "./loading-scene.tsx";
import { boundsOf, centreOf } from "./geometry.ts";
import type { Box } from "./geometry.ts";
import { apply, inside, invert, pointOf, segmentDistance, solve } from "./plane.ts";
import type { Matrix, Point } from "./plane.ts";
import { createSheetPainter, resolveColour, sheetPad } from "./sheet-painter.ts";
import type { Figure, Rgb, SheetPainter } from "./sheet-painter.ts";

export interface Marks {
  readonly answerIds: ReadonlySet<string>;
  readonly entities: readonly Entity[];
  readonly evidence: readonly EvidenceMark[];
  readonly hotIds: ReadonlySet<string>;
  readonly labels: ReadonlyMap<string, string>;
  readonly onHover: (id: string | null) => void;
  readonly onSelect: (id: string, add: boolean) => void;
  readonly selectedIds: readonly string[];
}

export interface Focus {
  readonly box: Box;
  readonly nonce: number;
}

export interface Measure {
  readonly onPoint: (point: readonly [number, number]) => void;
  readonly points: readonly (readonly [number, number])[];
}

export interface ViewerProps {
  readonly children?: ReactNode;
  readonly measure?: Measure | null;
  readonly onPainted?: () => void;
  readonly documentId: string;
  readonly focus: Focus | null;
  readonly marks: Marks;
  readonly page: Page;
}

type Mode = "top" | "3d";

interface Pose {
  tilt: number;
  turn: number;
  x: number;
  y: number;
  zoom: number;
}

interface Drag {
  readonly kind: "orbit" | "pan";
  moved: boolean;
  travel: number;
  x: number;
  y: number;
}

interface Nav {
  readonly cur: Pose;
  drag: Drag | null;
  readonly target: Pose;
}

interface Live {
  baked: number;
  fit: number;
  freeW: number;
  height: number;
  maxZoom: number;
  pageH: number;
  pageW: number;
  unit: number;
}

interface Projection {
  readonly back: Matrix;
  readonly forward: Matrix;
}

interface Frame {
  readonly freeRight: number;
  readonly height: number;
  readonly width: number;
}

interface Palette {
  readonly accent: Rgb;
  readonly ink: Rgb;
  readonly paper: Rgb;
}

const fallbackPalette: Palette = {
  accent: [47, 107, 255],
  ink: [17, 17, 18],
  paper: [236, 235, 231],
};

const tiltIn3d = 50;

const turnIn3d = -18;

const maxTilt = 62;

const minZoom = 0.35;

const sheetCap = 3600;

const perspective = 2600;

const poseKeys = ["tilt", "turn", "x", "y", "zoom"] as const;

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

const poseFor = (mode: Mode): Pose => ({
  tilt: mode === "3d" ? tiltIn3d : 0,
  turn: mode === "3d" ? turnIn3d : 0,
  x: 0,
  y: 0,
  zoom: 1,
});

const transformOf = (pose: Pose, baked: number) =>
  `translate3d(${pose.x.toFixed(2)}px, ${pose.y.toFixed(2)}px, 0) rotateX(${pose.tilt.toFixed(3)}deg) rotateZ(${pose.turn.toFixed(3)}deg) scale(${(pose.zoom / baked).toFixed(5)})`;

const sameRgb = (a: Rgb, b: Rgb) => a[0] === b[0] && a[1] === b[1] && a[2] === b[2];

const samePalette = (a: Palette, b: Palette) =>
  sameRgb(a.accent, b.accent) && sameRgb(a.ink, b.ink) && sameRgb(a.paper, b.paper);

const readPalette = (element: Element): Palette => {
  const style = getComputedStyle(element);

  return {
    accent: resolveColour(style.getPropertyValue("--desk-accent"), fallbackPalette.accent),
    ink: resolveColour(style.getPropertyValue("--desk-ink"), fallbackPalette.ink),
    paper: resolveColour(style.getPropertyValue("--desk-paper"), fallbackPalette.paper),
  };
};

const readFree = (element: Element, name: string) => {
  const raw = getComputedStyle(element).getPropertyValue(name).trim();
  const value = Number(raw.replace(/px$/u, ""));

  return Number.isFinite(value) ? Math.max(0, value) : 0;
};

const zoomPose = (target: Pose, factor: number, about: Point, maxZoom: number) => {
  const next = clamp(target.zoom * factor, minZoom, maxZoom);
  const ratio = next / target.zoom;

  target.x = about[0] - (about[0] - target.x) * ratio;
  target.y = about[1] - (about[1] - target.y) * ratio;
  target.zoom = next;
};

const figureOf = (
  item: Pick<Entity, "geometry" | "points">,
  tone: Rgb,
  style: Pick<Figure, "fillAlpha" | "lineAlpha" | "lineWidth">,
): Figure => ({ ...style, geometry: item.geometry, points: item.points, tone });

const hotStyle = { fillAlpha: 0.1, lineAlpha: 0.9, lineWidth: 1.2 };

const answerStyle = { fillAlpha: 0.3, lineAlpha: 1, lineWidth: 1.8 };

const selectedStyle = { fillAlpha: 0.45, lineAlpha: 1, lineWidth: 3 };

const figuresOf = (marks: Marks, palette: Palette) => {
  const hot = marks.entities.filter((entity) => marks.hotIds.has(entity.id));
  const answers = marks.entities.filter((entity) => marks.answerIds.has(entity.id));
  const selected = marks.entities.filter((entity) => marks.selectedIds.includes(entity.id));

  const figures: readonly Figure[] = [
    ...hot.map((entity) => figureOf(entity, palette.ink, hotStyle)),
    ...marks.evidence.map((mark) => figureOf(mark, palette.accent, hotStyle)),
    ...answers.map((entity) => figureOf(entity, palette.accent, answerStyle)),
    ...selected.map((entity) => figureOf(entity, palette.accent, selectedStyle)),
  ];

  const key = [
    hot.map((entity) => entity.id).join(","),
    marks.evidence.map((mark) => mark.id).join(","),
    answers.map((entity) => entity.id).join(","),
    marks.selectedIds.join(","),
    [palette.accent, palette.ink].map((colour) => colour.join(".")).join(","),
  ].join("|");

  return { figures, key };
};

const distanceTo = (entity: Entity, projection: Projection, screen: Point) => {
  const [first, second] = entity.points.map((point) => apply(projection.forward, pointOf(point)));

  if (first === undefined || (entity.geometry !== "point" && entity.geometry !== "line")) {
    return Number.POSITIVE_INFINITY;
  }

  if (entity.geometry === "line" && second !== undefined) {
    return segmentDistance(screen, first, second);
  }

  return Math.hypot(screen[0] - first[0], screen[1] - first[1]);
};

const nearOf = (entities: readonly Entity[], projection: Projection, screen: Point) => {
  const near = { distance: 10, id: "" };

  for (const entity of entities) {
    const distance = distanceTo(entity, projection, screen);

    if (distance < near.distance) {
      near.distance = distance;
      near.id = entity.id;
    }
  }

  return near.id === "" ? null : near.id;
};

const areaAt = (entity: Entity, at: Point) => {
  const box = boundsOf(entity.points);

  if (box === null || at[0] < box.x0 || at[0] > box.x1 || at[1] < box.y0 || at[1] > box.y1) {
    return null;
  }

  const contains =
    entity.geometry === "box" ||
    (entity.geometry === "polygon" && inside(entity.points.map(pointOf), at));

  return contains ? (box.x1 - box.x0) * (box.y1 - box.y0) : null;
};

const hitOf = (entities: readonly Entity[], projection: Projection, screen: Point) => {
  const near = nearOf(entities, projection, screen);

  if (near !== null) {
    return near;
  }

  const at = apply(projection.back, screen);
  const best = { area: Number.POSITIVE_INFINITY, id: "" };

  for (const entity of entities) {
    const area = areaAt(entity, at);

    if (area !== null && area < best.area) {
      best.area = area;
      best.id = entity.id;
    }
  }

  return best.id === "" ? null : best.id;
};

export const Viewer = ({
  children,
  documentId,
  focus,
  marks,
  measure: measuring,
  onPainted,
  page,
}: ViewerProps) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const tiltRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const painterRef = useRef<SheetPainter | null>(null);
  const projectionRef = useRef<Projection | null>(null);
  const hoverRef = useRef<string | null>(null);
  const staleRef = useRef(true);
  const bakeTimer = useRef(0);
  const focusNonce = useRef(0);
  const sheetSeen = useRef("");
  const navRef = useRef<Nav>({ cur: poseFor("top"), drag: null, target: poseFor("top") });

  const liveRef = useRef<Live>({
    baked: 1,
    fit: 1,
    freeW: 0,
    height: 0,
    maxZoom: 4,
    pageH: page.height,
    pageW: page.width,
    unit: 1,
  });

  const [frame, setFrame] = useState<Frame>({ freeRight: 0, height: 0, width: 0 });
  const [palette, setPalette] = useState<Palette>(fallbackPalette);
  const [mode, setMode] = useState<Mode>("top");
  const [bake, setBake] = useState(1);
  const [painted, setPainted] = useState(false);

  useEffect(() => {
    if (painted) {
      onPainted?.();
    }
  }, [onPainted, painted]);
  const sheetKey = `${documentId}:${String(page.index)}`;
  const [shownSheet, setShownSheet] = useState(sheetKey);

  if (shownSheet !== sheetKey) {
    setShownSheet(sheetKey);
    setBake(1);
  }

  const ready = frame.width > 0 && frame.height > 0;
  const freeW = Math.max(frame.width * 0.4, frame.width - frame.freeRight);
  const margin = clamp(Math.min(freeW, frame.height) * 0.06, 16, 48);

  const fit = ready
    ? Math.max(
        1e-4,
        Math.min(
          (freeW - 2 * margin) / Math.max(page.width, 1),
          (frame.height - 2 * margin) / Math.max(page.height, 1),
        ),
      )
    : 1;

  const baseW = page.width * fit;
  const sheetW = Math.max(1, Math.min(sheetCap, baseW * bake));
  const baked = sheetW / Math.max(baseW, 1e-6);
  const sheetH = (sheetW * page.height) / Math.max(page.width, 1);
  const pad = sheetPad(sheetW);
  const unit = sheetW / Math.max(page.width, 1);
  const maxZoom = Math.max(4, (sheetCap / Math.max(baseW, 1)) * 2);
  const screen = baked / Math.max(bake, 1e-6);
  const source = `/api/page?v=2&doc=${documentId}&page=${String(page.index)}`;
  const { figures, key: figuresKey } = figuresOf(marks, palette);

  const chips = marks.entities.flatMap((entity) => {
    const text = marks.labels.get(entity.id);

    return text === undefined ? [] : [{ at: centreOf(entity.points), id: entity.id, text }];
  });

  const scheduleBake = (zoom: number, delay: number) => {
    window.clearTimeout(bakeTimer.current);
    bakeTimer.current = window.setTimeout(() => {
      setBake(zoom);
    }, delay);
  };

  useLayoutEffect(() => {
    const live = liveRef.current;

    live.baked = baked;
    live.fit = fit;
    live.freeW = freeW;
    live.height = frame.height;
    live.maxZoom = maxZoom;
    live.pageH = page.height;
    live.pageW = page.width;
    live.unit = unit;
    staleRef.current = true;

    const tilt = tiltRef.current;

    if (tilt !== null) {
      tilt.style.transform = transformOf(navRef.current.cur, baked);
    }
  });

  useLayoutEffect(() => {
    if (sheetSeen.current === sheetKey) {
      return;
    }

    sheetSeen.current = sheetKey;

    const reset = poseFor("top");
    const nav = navRef.current;
    const root = rootRef.current;

    Object.assign(nav.cur, reset);
    Object.assign(nav.target, reset);
    nav.drag = null;

    if (root !== null) {
      const colours = readPalette(root);

      setPalette((current) => (samePalette(current, colours) ? current : colours));
    }
  }, [sheetKey]);

  useEffect(() => {
    const root = rootRef.current;

    if (root === null) {
      return;
    }

    const read = () => {
      const next: Frame = {
        freeRight: readFree(root, "--desk-free-right"),
        height: Math.max(
          root.clientHeight * 0.5,
          root.clientHeight - readFree(root, "--desk-free-bottom"),
        ),
        width: root.clientWidth,
      };

      const colours = readPalette(root);

      setFrame((current) =>
        current.width === next.width &&
        current.height === next.height &&
        current.freeRight === next.freeRight
          ? current
          : next,
      );
      setPalette((current) => (samePalette(current, colours) ? current : colours));
    };

    const resizes = new ResizeObserver(read);
    const themes = new MutationObserver(read);
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");

    resizes.observe(root);
    themes.observe(document.documentElement, {
      attributeFilter: ["class", "data-theme", "style"],
      attributes: true,
    });
    scheme.addEventListener("change", read);
    window.addEventListener("resize", read);

    return () => {
      resizes.disconnect();
      themes.disconnect();
      scheme.removeEventListener("change", read);
      window.removeEventListener("resize", read);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;

    if (canvas === null || !ready) {
      return;
    }

    const painter = painterRef.current ?? createSheetPainter(canvas);

    const look = {
      ink: palette.ink,
      inkUrl: `${source}&layer=ink`,
      pageHeight: page.height,
      pageWidth: page.width,
      paper: palette.paper,
      screen,
      sheetW,
      wallsUrl: `${source}&layer=walls`,
    };

    painterRef.current = painter;

    const timer = window.setTimeout(() => {
      painter
        .setLook(look)
        .then(() => {
          setPainted(true);

          return null;
        })
        .catch(() => {
          canvas.dataset.paint = "failed";
          setPainted(true);
        });
    }, 60);

    return () => {
      window.clearTimeout(timer);
    };
  }, [palette.ink, palette.paper, page.height, page.width, ready, screen, sheetW, source]);

  useEffect(() => {
    painterRef.current?.setMarks(figures, figuresKey);
  }, [figures, figuresKey]);

  useEffect(() => {
    if (focus === null || !ready || focus.nonce === focusNonce.current) {
      return;
    }

    focusNonce.current = focus.nonce;

    const live = liveRef.current;
    const { target } = navRef.current;
    const room = Math.min(110, Math.min(live.freeW, live.height) * 0.16);
    const boxW = Math.max(focus.box.x1 - focus.box.x0, 1);
    const boxH = Math.max(focus.box.y1 - focus.box.y0, 1);
    const scale = Math.min((live.freeW - 2 * room) / boxW, (live.height - 2 * room) / boxH, 2.2);
    const zoom = clamp(scale / live.fit, minZoom, live.maxZoom);
    const vx = ((focus.box.x0 + focus.box.x1) / 2 - live.pageW / 2) * live.fit * zoom;
    const vy = ((focus.box.y0 + focus.box.y1) / 2 - live.pageH / 2) * live.fit * zoom;
    const turn = (target.turn * Math.PI) / 180;
    const tilt = (target.tilt * Math.PI) / 180;

    target.zoom = zoom;
    target.x = -(vx * Math.cos(turn) - vy * Math.sin(turn));
    target.y = -(vx * Math.sin(turn) + vy * Math.cos(turn)) * Math.cos(tilt);
    window.clearTimeout(bakeTimer.current);
    bakeTimer.current = window.setTimeout(() => {
      setBake(zoom);
    }, 520);
  }, [focus, ready]);

  useEffect(() => {
    const root = rootRef.current;

    if (root === null) {
      return;
    }

    const onWheel = (event: WheelEvent) => {
      const stage = stageRef.current;
      const node = event.target;

      if (stage === null || !(node instanceof Node) || (node !== root && !stage.contains(node))) {
        return;
      }

      event.preventDefault();

      const rect = root.getBoundingClientRect();
      const live = liveRef.current;
      const { target } = navRef.current;

      const about: Point = [
        event.clientX - rect.left - live.freeW / 2,
        event.clientY - rect.top - live.height / 2,
      ];

      zoomPose(
        target,
        Math.exp(-event.deltaY * (event.ctrlKey ? 0.012 : 0.0022)),
        about,
        live.maxZoom,
      );
      window.clearTimeout(bakeTimer.current);
      bakeTimer.current = window.setTimeout(() => {
        setBake(target.zoom);
      }, 260);
    };

    root.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      root.removeEventListener("wheel", onWheel);
      window.clearTimeout(bakeTimer.current);
    };
  }, []);

  useEffect(() => {
    const seen = { key: "" };
    const loop = { handle: 0 };

    const measure = (root: HTMLDivElement) => {
      const live = liveRef.current;
      const { cur } = navRef.current;
      const rect = root.getBoundingClientRect();
      const pivot: Point = [live.freeW / 2, live.height / 2];
      const previous = projectionRef.current;
      const under = previous === null ? null : apply(previous.back, pivot);

      const centre: Point =
        under === null || !Number.isFinite(under[0]) || !Number.isFinite(under[1])
          ? [live.pageW / 2, live.pageH / 2]
          : [clamp(under[0], 0, live.pageW), clamp(under[1], 0, live.pageH)];

      const reach = 180 / Math.max(live.fit * cur.zoom, 1e-6);

      const quad: readonly Point[] = [
        [centre[0] - reach, centre[1] - reach],
        [centre[0] + reach, centre[1] - reach],
        [centre[0] + reach, centre[1] + reach],
        [centre[0] - reach, centre[1] + reach],
      ];

      const anchors = [...root.querySelectorAll<HTMLElement>("[data-quad]")];
      const placed: Point[] = [];

      for (const [index, anchor] of anchors.entries()) {
        const [x, y] = quad[index] ?? centre;

        anchor.style.left = `${String(x * live.unit)}px`;
        anchor.style.top = `${String(y * live.unit)}px`;
      }

      for (const anchor of anchors) {
        const at = anchor.getBoundingClientRect();

        placed.push([at.left - rect.left, at.top - rect.top]);
      }

      const forward = solve(quad, placed);
      const back = forward === null ? null : invert(forward);

      projectionRef.current = forward === null || back === null ? null : { back, forward };

      for (const chip of root.querySelectorAll<HTMLElement>("[data-chip]")) {
        const spot =
          forward === null
            ? null
            : apply(forward, [Number(chip.dataset.x ?? 0), Number(chip.dataset.y ?? 0)]);

        if (spot === null || !Number.isFinite(spot[0]) || !Number.isFinite(spot[1])) {
          chip.style.visibility = "hidden";
        } else {
          chip.style.transform = `translate(${spot[0].toFixed(1)}px, ${spot[1].toFixed(1)}px) translate(-50%, -50%)`;
          chip.style.visibility = "visible";
        }
      }
    };

    const step = () => {
      const root = rootRef.current;
      const tilt = tiltRef.current;
      const live = liveRef.current;
      const nav = navRef.current;

      if (root !== null && tilt !== null) {
        for (const name of poseKeys) {
          const gap = nav.target[name] - nav.cur[name];

          nav.cur[name] = Math.abs(gap) < 0.0005 ? nav.target[name] : nav.cur[name] + gap * 0.22;
        }

        const key = [
          ...poseKeys.map((name) => nav.cur[name].toFixed(4)),
          live.baked,
          live.freeW,
          live.height,
        ].join(",");

        if (key !== seen.key || staleRef.current) {
          seen.key = key;
          staleRef.current = false;
          tilt.style.transform = transformOf(nav.cur, live.baked);
          measure(root);
        }

        painterRef.current?.draw(nav.cur.tilt, nav.cur.turn);
      }

      loop.handle = requestAnimationFrame(step);
    };

    loop.handle = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(loop.handle);
    };
  }, []);

  const hitAt = (clientX: number, clientY: number) => {
    const root = rootRef.current;
    const projection = projectionRef.current;

    if (root === null || projection === null) {
      return null;
    }

    const rect = root.getBoundingClientRect();

    return hitOf(marks.entities, projection, [clientX - rect.left, clientY - rect.top]);
  };

  const pageAt = (clientX: number, clientY: number): readonly [number, number] | null => {
    const root = rootRef.current;
    const projection = projectionRef.current;

    if (root === null || projection === null) {
      return null;
    }

    const rect = root.getBoundingClientRect();
    const [x, y] = apply(projection.back, [clientX - rect.left, clientY - rect.top]);

    return x >= 0 && y >= 0 && x <= page.width && y <= page.height ? [x, y] : null;
  };

  const hover = (id: string | null) => {
    if (id === hoverRef.current) {
      return;
    }

    hoverRef.current = id;

    const root = rootRef.current;

    if (root !== null) {
      root.dataset.hit = id === null ? "false" : "true";
    }

    marks.onHover(id);
  };

  const onStage = (node: EventTarget, root: HTMLElement) => {
    const stage = stageRef.current;

    return node instanceof Node && (node === root || (stage !== null && stage.contains(node)));
  };

  const changeMode = (next: Mode) => {
    const { target } = navRef.current;
    const pose = poseFor(next);

    target.tilt = pose.tilt;
    target.turn = pose.turn;
    setMode(next);
  };

  const zoomStep = (factor: number) => {
    const { target } = navRef.current;

    zoomPose(target, factor, [0, 0], liveRef.current.maxZoom);
    scheduleBake(target.zoom, 400);
  };

  const reset = () => {
    Object.assign(navRef.current.target, poseFor(mode));
    scheduleBake(1, 400);
  };

  const onKey = (event: KeyboardEvent) => {
    const typing =
      event.target instanceof HTMLElement &&
      (event.target.isContentEditable ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName));

    if (typing || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }

    const actions = new Map<string, () => void>(
      Object.entries({
        "+": () => {
          zoomStep(1.4);
        },
        "-": () => {
          zoomStep(1 / 1.4);
        },
        "0": reset,
        "2": () => {
          changeMode("top");
        },
        "3": () => {
          changeMode("3d");
        },
        "=": () => {
          zoomStep(1.4);
        },
        v: () => {
          changeMode(mode === "top" ? "3d" : "top");
        },
      }),
    );

    actions.get(event.key.toLowerCase())?.();
  };

  const keyRef = useRef(onKey);

  useEffect(() => {
    keyRef.current = onKey;
  });

  useEffect(() => {
    const listen = (event: KeyboardEvent) => {
      keyRef.current(event);
    };

    window.addEventListener("keydown", listen);

    return () => {
      window.removeEventListener("keydown", listen);
    };
  }, []);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.button !== 0 && event.button !== 2) || !onStage(event.target, event.currentTarget)) {
      return;
    }

    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      navRef.current.drag = null;
    }

    const orbit = event.button === 2 || (mode === "3d" && !event.shiftKey);

    navRef.current.drag = {
      kind: orbit ? "orbit" : "pan",
      moved: false,
      travel: 0,
      x: event.clientX,
      y: event.clientY,
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const nav = navRef.current;
    const { drag } = nav;

    if (drag === null) {
      hover(
        onStage(event.target, event.currentTarget) ? hitAt(event.clientX, event.clientY) : null,
      );

      return;
    }

    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;

    drag.x = event.clientX;
    drag.y = event.clientY;
    drag.travel += Math.abs(dx) + Math.abs(dy);

    if (drag.travel < 4) {
      return;
    }

    if (!drag.moved) {
      drag.moved = true;
      hover(null);

      if (drag.kind === "orbit" && mode !== "3d") {
        setMode("3d");
      }
    }

    if (drag.kind === "orbit") {
      nav.target.turn += dx * 0.3;
      nav.target.tilt = clamp(nav.target.tilt - dy * 0.3, 0, maxTilt);
    } else {
      nav.target.x += dx;
      nav.target.y += dy;
    }
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    const { drag } = navRef.current;

    navRef.current.drag = null;

    if (drag === null || drag.moved || event.button !== 0) {
      return;
    }

    if (measuring !== null && measuring !== undefined) {
      const at = pageAt(event.clientX, event.clientY);

      if (at !== null) {
        measuring.onPoint(at);
      }

      return;
    }

    const id = hitAt(event.clientX, event.clientY);

    if (id !== null) {
      marks.onSelect(id, event.shiftKey);
    }
  };

  const onPointerCancel = () => {
    navRef.current.drag = null;
  };

  return (
    <div
      className="desk-canvas relative h-full touch-none overflow-hidden select-none"
      data-measuring={measuring === null || measuring === undefined ? undefined : ""}
      data-mode={mode}
      data-testid="viewer"
      onContextMenu={(event) => {
        event.preventDefault();
      }}
      onPointerCancel={onPointerCancel}
      onPointerDown={onPointerDown}
      onPointerLeave={() => {
        if (navRef.current.drag === null) {
          hover(null);
        }
      }}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      ref={rootRef}
      style={{ perspective }}
    >
      <div className="absolute inset-0" ref={stageRef}>
        <div
          className="absolute h-0 w-0"
          ref={tiltRef}
          style={{
            left: freeW / 2,
            opacity: ready ? 1 : 0,
            top: frame.height / 2,
            transformStyle: "preserve-3d",
            transition: "opacity 300ms",
            willChange: "transform",
          }}
        >
          <div
            className="absolute"
            style={{
              height: sheetH,
              left: (-page.width / 2) * unit,
              top: (-page.height / 2) * unit,
              transformStyle: "preserve-3d",
              width: sheetW,
            }}
          >
            <canvas
              aria-hidden="true"
              className="absolute block"
              ref={canvasRef}
              style={{ height: sheetH + 2 * pad, left: -pad, top: -pad, width: sheetW + 2 * pad }}
            />
            {[0, 1, 2, 3].map((index) => (
              <i className="absolute h-0 w-0" data-quad={index} key={index} />
            ))}
          </div>
        </div>
      </div>
      {chips.map((chip) => (
        <span
          className="desk-chip-tag pointer-events-none absolute top-0 left-0"
          data-chip=""
          data-x={chip.at[0]}
          data-y={chip.at[1]}
          key={chip.id}
          style={{ visibility: "hidden" }}
        >
          {chip.text}
        </span>
      ))}
      {(measuring?.points ?? []).map((point, index) => (
        <span
          className="desk-measure-dot pointer-events-none absolute top-0 left-0"
          data-chip=""
          data-x={point[0]}
          data-y={point[1]}
          key={index === 0 ? "a" : "b"}
          style={{ visibility: "hidden" }}
        >
          {index === 0 ? "A" : "B"}
        </span>
      ))}
      {painted ? null : (
        <div
          className="pointer-events-none absolute inset-y-0 left-0 grid place-items-center"
          data-testid="drawing-wait"
          style={{ width: freeW }}
        >
          <div className="flex flex-col items-center text-center">
            <LoadingScene step={4} />
            <p aria-live="polite" className="text-lg font-medium">
              Drawing the page
            </p>
          </div>
        </div>
      )}
      {children}
      <div
        className="desk-viewpill absolute top-4 left-4"
        onPointerDown={(event) => {
          event.stopPropagation();
        }}
      >
        <fieldset className="desk-seg">
          <legend className="sr-only">View</legend>
          <button
            aria-pressed={mode === "top"}
            title="View from above (key 2, or V to switch)"
            onClick={() => {
              changeMode("top");
            }}
            type="button"
          >
            Top
          </button>
          <button
            aria-pressed={mode === "3d"}
            title="3D view (key 3, or V to switch)"
            onClick={() => {
              changeMode("3d");
            }}
            type="button"
          >
            3D
          </button>
        </fieldset>
        <button
          aria-label="Zoom out"
          className="desk-round"
          onClick={() => {
            zoomStep(1 / 1.4);
          }}
          type="button"
        >
          <Minus aria-hidden="true" size={16} />
        </button>
        <button
          aria-label="Zoom in"
          className="desk-round"
          onClick={() => {
            zoomStep(1.4);
          }}
          type="button"
        >
          <Plus aria-hidden="true" size={16} />
        </button>
        <button aria-label="Reset the view" className="desk-round" onClick={reset} type="button">
          <RotateCcw aria-hidden="true" size={16} />
        </button>
      </div>
    </div>
  );
};
