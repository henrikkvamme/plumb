import {
  BackSide,
  Box3,
  BufferAttribute,
  BufferGeometry,
  DirectionalLight,
  DoubleSide,
  EdgesGeometry,
  FrontSide,
  Group,
  HemisphereLight,
  LineBasicMaterial,
  LineSegments,
  MOUSE,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  NeutralToneMapping,
  PerspectiveCamera,
  Plane,
  Raycaster,
  SRGBColorSpace,
  Scene,
  Spherical,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three";
import type { Intersection } from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";

import type { BuildingModel, ModelGroup, ModelMesh } from "./model-payload.ts";
import { floorPlates, matchesRoom, roomText } from "./model-rooms.ts";
import type { Room } from "./model-rooms.ts";
import { bakeContactShadow, markForShadow } from "./model-shadow.ts";

export type ViewMode = "plan" | "cutaway" | "building" | "exploded";

export const viewModes: readonly ViewMode[] = ["plan", "cutaway", "building", "exploded"];

export interface StageState {
  readonly furniture: boolean;
  readonly storey: number;
  readonly view: ViewMode;
}

export interface ModelStage {
  readonly clear: () => void;
  readonly dispose: () => void;
  readonly frame: () => void;
  readonly mark: (names: readonly string[]) => void;
  readonly reset: () => void;
  readonly setFurniture: (on: boolean) => void;
  readonly setStorey: (storey: number) => void;
  readonly setView: (view: ViewMode) => void;
  readonly shownStoreys: readonly number[];
  readonly zoom: (factor: number) => void;
}

export interface StageEvents {
  readonly onHover: (label: string | null) => void;
  readonly onState: (state: StageState) => void;
}

export interface StageHost {
  readonly canvasHost: HTMLElement;
  readonly labels: HTMLElement;
  readonly tag: HTMLElement;
}

type PartKind = "furniture" | "glass" | "plate" | "solid";

type Presence = "ghost" | "hidden" | "normal";

interface Fade {
  from: number;
  to: number;
  value: number;
}

interface Level {
  readonly bounds: Box3;
  readonly cutBase: number;
  readonly elevation: number;
  readonly group: Group;
  readonly index: number;
  readonly lift: Fade;
  readonly plane: Plane;
  readonly poche: MeshBasicMaterial;
  cut: boolean;
  delay: number;
}

interface Part {
  readonly edges: LineSegments | null;
  readonly fill: MeshStandardMaterial;
  readonly fillFade: Fade;
  readonly kind: PartKind;
  readonly level: Level;
  readonly line: LineBasicMaterial | null;
  readonly lineFade: Fade;
  readonly mesh: Mesh;
  readonly poche: Mesh | null;
  readonly source: ModelMesh;
  readonly starts: Uint32Array;
  presence: Presence;
}

interface Range {
  readonly count: number;
  readonly first: number;
  readonly part: Part;
}

interface Pose {
  readonly fov: number;
  readonly phi: number;
  readonly radius: number;
  readonly target: Vector3;
  readonly theta: number;
}

interface CameraTween {
  readonly duration: number;
  readonly ease: (t: number) => number;
  readonly from: Pose;
  readonly start: number;
  readonly to: Pose;
}

interface Highlight {
  readonly dispose: () => void;
  readonly element: number;
  readonly label: HTMLElement | null;
  readonly room: Room | null;
}

const palette: Record<ModelGroup, string> = {
  beam: "#efede8",
  column: "#f4f3ef",
  door: "#e9e5dc",
  furniture: "#dcd8d0",
  glass: "#cfdce6",
  other: "#ebe9e3",
  roof: "#dedad2",
  slab: "#e4e2dc",
  space: "#ebe7de",
  stair: "#eeece6",
  wall: "#f7f6f2",
  window: "#f1f0ec",
};

const open = 1e5;

const cutHeight = 1.2;

const flatFov = 2.4;

const wideFov = 23;

const topPhi = 0.0001;

const glassOpacity = 0.25;

const lineOpacity = 0.45;

const ghostFill = 0.08;

const ghostLine = 0.12;

const tweenMs = 700;

const staggerMs = 70;

const topInset = 72;

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

const easeOut = (t: number) => 1 - (1 - t) ** 3;

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

const mix = (from: number, to: number, t: number) => from + (to - from) * t;

const readPixels = (element: Element, name: string) => {
  const value = Number(getComputedStyle(element).getPropertyValue(name).trim().replace(/px$/u, ""));

  return Number.isFinite(value) ? value : 0;
};

const readColour = (element: Element, name: string, fallback: string) => {
  const value = getComputedStyle(element).getPropertyValue(name).trim();

  return value === "" ? fallback : value;
};

const kindOf = (group: ModelGroup): PartKind => {
  if (group === "glass") {
    return "glass";
  }

  if (group === "furniture") {
    return "furniture";
  }

  if (group === "space") {
    return "plate";
  }

  return "solid";
};

const spanStarts = (spans: Uint32Array) => {
  const starts = new Uint32Array(spans.length / 3);

  for (let index = 0; index < starts.length; index += 1) {
    starts[index] = spans[index * 3 + 1] ?? 0;
  }

  return starts;
};

const spanAt = (starts: Uint32Array, face: number) => {
  let low = 0;
  let high = starts.length - 1;

  while (low < high) {
    const middle = Math.ceil((low + high) / 2);

    if ((starts[middle] ?? 0) <= face) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }

  return low;
};

const elementAt = (part: Part, face: number) =>
  part.source.spans[spanAt(part.starts, face) * 3] ?? -1;

const nearestAngle = (from: number, to: number) => {
  const turn = Math.PI * 2;
  const delta = ((((to - from) % turn) + turn * 1.5) % turn) - Math.PI;

  return from + delta;
};

const offsetOf = (phi: number, theta: number, radius: number) =>
  new Vector3().setFromSpherical(new Spherical(radius, phi, theta));

const fillTarget = (kind: PartKind, presence: Presence) => {
  if (presence === "hidden") {
    return 0;
  }

  if (presence === "ghost") {
    return kind === "glass" ? ghostFill / 2 : ghostFill;
  }

  return kind === "glass" ? glassOpacity : 1;
};

const lineTarget = (kind: PartKind, presence: Presence) => {
  if (presence === "hidden") {
    return 0;
  }

  if (presence === "ghost") {
    return ghostLine;
  }

  return kind === "glass" ? lineOpacity / 2 : lineOpacity;
};

export const mountModel = (
  host: StageHost,
  model: BuildingModel,
  events: StageEvents,
): ModelStage => {
  const { canvasHost, labels, tag } = host;
  const renderer = new WebGLRenderer({ alpha: true, antialias: true });

  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = NeutralToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.localClippingEnabled = true;
  renderer.setClearColor("#000000", 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const canvas = renderer.domElement;

  canvas.className = "absolute inset-0 block h-full w-full touch-none outline-none";
  canvas.style.opacity = "0";
  canvas.style.transition = "opacity 500ms ease";
  canvasHost.append(canvas);

  const ink = readColour(canvasHost, "--desk-ink", "#111112");
  const accent = readColour(canvasHost, "--desk-accent", "#2f6bff");
  const scene = new Scene();
  const camera = new PerspectiveCamera(flatFov, 1, 0.05, 4000);
  const controls = new OrbitControls(camera, canvas);

  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.zoomToCursor = true;
  controls.screenSpacePanning = true;
  controls.rotateSpeed = 0.6;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;

  const hemisphere = new HemisphereLight("#ffffff", "#d8d6d0", 2.3);
  const sun = new DirectionalLight("#ffffff", 1.5);

  scene.add(hemisphere, sun, sun.target);

  const disposables: { dispose: () => void }[] = [];
  const levels = new Map<number, Level>();

  const levelOf = (index: number) => {
    const found = levels.get(index);

    if (found !== undefined) {
      return found;
    }

    const elevation = model.storeys[index]?.elevation ?? 0;
    const plane = new Plane(new Vector3(0, -1, 0), open);
    const poche = new MeshBasicMaterial({ clippingPlanes: [plane], color: ink, side: BackSide });
    const group = new Group();

    const made: Level = {
      bounds: new Box3(),
      cut: false,
      cutBase: elevation + cutHeight,
      delay: 0,
      elevation,
      group,
      index,
      lift: { from: 0, to: 0, value: 0 },
      plane,
      poche,
    };

    disposables.push(poche);
    scene.add(group);
    levels.set(index, made);

    return made;
  };

  const parts: Part[] = [];
  const ranges = new Map<number, Range[]>();
  const rooms = new Map<number, Room>();
  const bounds = new Box3();

  const addPart = (source: ModelMesh) => {
    const kind = kindOf(source.group);
    const level = levelOf(source.storey);
    const geometry = new BufferGeometry();

    geometry.setAttribute("position", new BufferAttribute(source.positions, 3));
    geometry.setIndex(new BufferAttribute(source.indices, 1));
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    disposables.push(geometry);

    const fill = new MeshStandardMaterial({
      clippingPlanes: [level.plane],
      color: palette[source.group],
      depthWrite: kind !== "glass",
      flatShading: true,
      metalness: 0,
      opacity: 0,
      polygonOffset: true,
      polygonOffsetFactor: kind === "plate" ? -1 : 1,
      polygonOffsetUnits: kind === "plate" ? -1 : 1,
      roughness: 0.9,
      side: DoubleSide,
      transparent: true,
    });

    disposables.push(fill);

    const mesh = new Mesh(geometry, fill);

    mesh.visible = false;
    mesh.renderOrder = kind === "glass" ? 2 : 0;
    level.group.add(mesh);

    let edges: LineSegments | null = null;
    let line: LineBasicMaterial | null = null;

    if (kind === "solid" || kind === "glass") {
      const lines = new EdgesGeometry(geometry, 28);

      line = new LineBasicMaterial({
        clippingPlanes: [level.plane],
        color: ink,
        opacity: 0,
        transparent: true,
      });

      edges = new LineSegments(lines, line);
      edges.visible = false;
      level.group.add(edges);
      disposables.push(lines, line);
    }

    let poche: Mesh | null = null;

    if (kind === "solid" || kind === "furniture") {
      poche = new Mesh(geometry, level.poche);
      poche.visible = false;
      level.group.add(poche);
    }

    if (kind === "solid") {
      markForShadow(mesh);

      if (geometry.boundingBox !== null) {
        bounds.union(geometry.boundingBox);

        if (source.group !== "roof") {
          level.bounds.union(geometry.boundingBox);
        }
      }
    }

    const part: Part = {
      edges,
      fill,
      fillFade: { from: 0, to: 0, value: 0 },
      kind,
      level,
      line,
      lineFade: { from: 0, to: 0, value: 0 },
      mesh,
      poche,
      presence: "hidden",
      source,
      starts: spanStarts(source.spans),
    };

    parts.push(part);

    for (let index = 0; index < part.starts.length; index += 1) {
      const element = source.spans[index * 3] ?? 0;
      const list = ranges.get(element) ?? [];

      list.push({
        count: source.spans[index * 3 + 2] ?? 0,
        first: source.spans[index * 3 + 1] ?? 0,
        part,
      });

      ranges.set(element, list);
    }
  };

  for (const source of model.meshes) {
    if (source.group === "space") {
      const plates = floorPlates(source);

      for (const room of plates.rooms) {
        rooms.set(room.element, room);
      }

      if (plates.mesh.indices.length > 0) {
        addPart(plates.mesh);
      }
    } else {
      addPart(source);
    }
  }

  if (bounds.isEmpty()) {
    bounds.set(new Vector3(-5, 0, -5), new Vector3(5, 3, 5));
  }

  const centre = bounds.getCenter(new Vector3());
  const size = bounds.getSize(new Vector3());
  const reach = Math.max(size.x, size.y, size.z, 4);

  sun.position.set(-reach * 0.7, reach * 1.6, reach * 1.1);

  const shownStoreys = [...levels.values()]
    .flatMap((level) => (level.index >= 0 && !level.bounds.isEmpty() ? [level.index] : []))
    .toSorted((a, b) => (model.storeys[a]?.elevation ?? 0) - (model.storeys[b]?.elevation ?? 0));

  const lifts = new Map<number, number>();
  let stack = 0;

  for (const [order, index] of shownStoreys.entries()) {
    lifts.set(index, stack);

    const next = shownStoreys[order + 1];

    const height =
      next === undefined
        ? 3
        : (model.storeys[next]?.elevation ?? 0) - (model.storeys[index]?.elevation ?? 0);

    stack += clamp(height, 2.4, 8);
  }

  const withRooms = shownStoreys.find((index) =>
    [...rooms.keys()].some((element) => model.elements[element]?.storey === index),
  );

  const defaultStorey = withRooms ?? shownStoreys[0] ?? -1;

  for (const part of parts) {
    part.mesh.visible = part.kind === "solid";
  }

  const shadow = bakeContactShadow(renderer, scene, bounds, 0.35);

  for (const part of parts) {
    part.mesh.visible = false;
  }

  scene.add(shadow.mesh);
  disposables.push(shadow);

  let view: ViewMode = "cutaway";
  let storey = defaultStorey;
  let furniture = false;
  let width = 1;
  let height = 1;
  let freeRight = 0;
  let freeBottom = 0;
  let cameraTween: CameraTween | null = null;
  let layerStart = 0;
  let layerEnd = 0;
  let frame = 0;
  let pickFrame = 0;
  let hovered = -1;
  let hover: Highlight | null = null;
  let selection: Highlight | null = null;
  let marks: Highlight[] = [];
  let down: { readonly time: number; readonly x: number; readonly y: number } | null = null;
  const pointer = new Vector2();
  const raycaster = new Raycaster();
  const lineMaterials = new Set<LineMaterial>();

  const presenceOf = (part: Part): Presence => {
    const { index } = part.level;

    if (part.kind === "furniture" && !furniture) {
      return "hidden";
    }

    if (view === "building") {
      return part.kind === "plate" ? "hidden" : "normal";
    }

    if (index < 0 || part.source.group === "roof") {
      return "hidden";
    }

    if (view === "exploded") {
      return "normal";
    }

    if (index === storey) {
      return "normal";
    }

    const below = (model.storeys[index]?.elevation ?? 0) < (model.storeys[storey]?.elevation ?? 0);

    return below && part.kind !== "plate" ? "ghost" : "hidden";
  };

  const applyLayers = (now: number) => {
    const exploded = view === "exploded";

    for (const level of levels.values()) {
      level.cut = view !== "building" && (exploded || level.index === storey);
      level.lift.from = level.lift.value;
      level.lift.to = exploded ? (lifts.get(level.index) ?? 0) : 0;

      const order = shownStoreys.indexOf(level.index);

      level.delay = exploded && order !== -1 ? order * staggerMs : 0;
    }

    for (const part of parts) {
      part.presence = presenceOf(part);
      part.fillFade.from = part.fillFade.value;
      part.fillFade.to = fillTarget(part.kind, part.presence);
      part.lineFade.from = part.lineFade.value;
      part.lineFade.to = lineTarget(part.kind, part.presence);

      const side =
        part.level.cut && part.kind !== "glass" && part.kind !== "plate" ? FrontSide : DoubleSide;

      if (part.fill.side !== side) {
        part.fill.side = side;
        part.fill.needsUpdate = true;
      }
    }

    layerStart = now;
    layerEnd = now + tweenMs + shownStoreys.length * staggerMs;
  };

  const stepLayers = (now: number) => {
    if (layerEnd === 0) {
      return false;
    }

    for (const level of levels.values()) {
      const t = easeInOut(clamp((now - layerStart - level.delay) / tweenMs, 0, 1));

      level.lift.value = mix(level.lift.from, level.lift.to, t);
      level.group.position.y = level.lift.value;
      level.plane.constant = level.cut ? level.cutBase + level.lift.value : open;
    }

    for (const part of parts) {
      const t = easeInOut(clamp((now - layerStart - part.level.delay) / tweenMs, 0, 1));
      const fill = mix(part.fillFade.from, part.fillFade.to, t);
      const solid = fill >= 0.999 && part.kind !== "glass";

      part.fillFade.value = fill;
      part.fill.opacity = fill;
      part.fill.transparent = !solid;
      part.fill.depthWrite = solid || (part.kind !== "glass" && fill > 0.5);
      part.mesh.visible = fill > 0.002;
      part.lineFade.value = mix(part.lineFade.from, part.lineFade.to, t);

      if (part.line !== null && part.edges !== null) {
        part.line.opacity = part.lineFade.value;
        part.edges.visible = part.lineFade.value > 0.002;
      }

      if (part.poche !== null) {
        part.poche.visible = part.level.cut && part.presence === "normal" && fill > 0.98;
      }
    }

    if (now >= layerEnd) {
      layerEnd = 0;

      return false;
    }

    return true;
  };

  const levelBox = (level: Level, lift: number) => {
    const box = level.bounds.clone();

    if (box.isEmpty()) {
      return box;
    }

    box.min.y = Math.max(box.min.y, level.elevation - 0.25);
    box.max.y = Math.min(box.max.y, level.cutBase);
    box.min.y += lift;
    box.max.y += lift;

    return box;
  };

  const viewBox = () => {
    if (view === "building") {
      return bounds.clone();
    }

    if (view === "exploded") {
      const box = new Box3();

      for (const index of shownStoreys) {
        const level = levels.get(index);

        if (level !== undefined) {
          box.union(levelBox(level, lifts.get(index) ?? 0));
        }
      }

      return box.isEmpty() ? bounds.clone() : box;
    }

    const level = levels.get(storey);
    const box = level === undefined ? new Box3() : levelBox(level, 0);

    return box.isEmpty() ? bounds.clone() : box;
  };

  const fitRadius = (
    box: Box3,
    target: Vector3,
    pose: { phi: number; theta: number; fov: number },
  ) => {
    const forward = offsetOf(pose.phi, pose.theta, 1).negate();
    const right = new Vector3().crossVectors(forward, new Vector3(0, 1, 0)).normalize();
    const up = new Vector3().crossVectors(right, forward).normalize();
    const half = Math.tan((pose.fov * Math.PI) / 360);
    const tanV = (half * Math.max(1, height - freeBottom - topInset - 24)) / height;
    const tanH = (half * Math.max(1, width - freeRight - 40)) / height;
    let needed = 0;

    for (const x of [box.min.x, box.max.x]) {
      for (const y of [box.min.y, box.max.y]) {
        for (const z of [box.min.z, box.max.z]) {
          const corner = new Vector3(x, y, z).sub(target);
          const depth = corner.dot(forward);

          needed = Math.max(
            needed,
            depth + Math.abs(corner.dot(right)) / tanH,
            depth + Math.abs(corner.dot(up)) / tanV,
          );
        }
      }
    }

    return needed * 1.06;
  };

  const anglesOf = (mode: ViewMode) => {
    if (mode === "plan") {
      return { fov: flatFov, phi: topPhi, theta: 0 };
    }

    if (mode === "building") {
      return { fov: wideFov, phi: 1.13, theta: Math.PI * 0.25 };
    }

    if (mode === "exploded") {
      return { fov: flatFov, phi: 1, theta: Math.PI * 0.25 };
    }

    return { fov: flatFov, phi: 0.61, theta: Math.PI * 0.25 };
  };

  const poseFor = (box: Box3, angles: { phi: number; theta: number; fov: number }): Pose => {
    const target = box.getCenter(new Vector3());

    return { ...angles, radius: fitRadius(box, target, angles), target };
  };

  const homePose = () => poseFor(viewBox(), anglesOf(view));

  const currentPose = (): Pose => {
    const offset = new Spherical().setFromVector3(camera.position.clone().sub(controls.target));

    return {
      fov: camera.fov,
      phi: offset.phi,
      radius: offset.radius,
      target: controls.target.clone(),
      theta: offset.theta,
    };
  };

  const placeCamera = (pose: Pose) => {
    controls.target.copy(pose.target);
    camera.position.copy(offsetOf(pose.phi, pose.theta, pose.radius).add(pose.target));
    camera.fov = pose.fov;
    camera.lookAt(pose.target);
  };

  const stepCamera = (now: number) => {
    if (cameraTween === null) {
      return false;
    }

    const progress = clamp((now - cameraTween.start) / cameraTween.duration, 0, 1);
    const t = cameraTween.ease(progress);
    const { from, to } = cameraTween;
    const theta = nearestAngle(from.theta, to.theta);
    const tanFrom = Math.tan((from.fov * Math.PI) / 360);
    const tanTo = Math.tan((to.fov * Math.PI) / 360);
    const tanNow = Math.exp(mix(Math.log(tanFrom), Math.log(tanTo), t));
    const sizeFrom = from.radius * tanFrom;
    const sizeTo = to.radius * tanTo;
    const sizeNow = Math.exp(mix(Math.log(sizeFrom), Math.log(sizeTo), t));

    placeCamera({
      fov: (Math.atan(tanNow) * 360) / Math.PI,
      phi: mix(from.phi, to.phi, t),
      radius: sizeNow / tanNow,
      target: from.target.clone().lerp(to.target, t),
      theta: mix(from.theta, theta, t),
    });

    if (progress >= 1) {
      cameraTween = null;
      controls.enabled = true;

      return false;
    }

    return true;
  };

  const updateDepth = () => {
    const distance = camera.position.distanceTo(controls.target);

    const spread =
      reach * 1.3 + controls.target.distanceTo(centre) + (view === "exploded" ? stack : 0);

    camera.near = Math.max(distance * 0.002, distance - spread, 0.01);
    camera.far = distance + spread;
    camera.updateProjectionMatrix();
  };

  const project = new Vector3();

  const placeLabel = (item: Highlight) => {
    if (item.label === null || item.room === null) {
      return;
    }

    const level = levels.get(model.elements[item.element]?.storey ?? -1);
    const lift = level === undefined ? 0 : level.lift.value;

    project.set(item.room.x, item.room.y + lift, item.room.z).project(camera);

    const x = ((project.x + 1) / 2) * width;
    const y = ((1 - project.y) / 2) * height;
    const shown = project.z < 1 && level !== undefined && level.group.visible;

    item.label.style.visibility = shown ? "visible" : "hidden";
    item.label.style.transform = `translate(${String(Math.round(x))}px, ${String(Math.round(y))}px) translate(-50%, -50%)`;
  };

  const placeLabels = () => {
    if (selection !== null) {
      placeLabel(selection);
    }

    for (const item of marks) {
      placeLabel(item);
    }
  };

  const tick = (now: number) => {
    frame = 0;

    const moving = stepCamera(now);
    const fading = stepLayers(now);

    if (!moving) {
      controls.update();
    }

    updateDepth();
    renderer.render(scene, camera);
    placeLabels();
    canvas.style.opacity = "1";

    if (moving || fading) {
      frame = requestAnimationFrame(tick);
    }
  };

  const request = () => {
    if (frame === 0) {
      frame = requestAnimationFrame(tick);
    }
  };

  const limitsFor = (pose: Pose) => {
    controls.minDistance = pose.radius * 0.06;
    controls.maxDistance = pose.radius * 4;
  };

  const animateTo = (to: Pose, duration = tweenMs, ease = easeInOut) => {
    cameraTween = { duration, ease, from: currentPose(), start: performance.now(), to };
    controls.enabled = false;
    request();
  };

  const rangeBox = (element: number) => {
    const box = new Box3();

    for (const range of ranges.get(element) ?? []) {
      const { indices, positions } = range.part.source;
      const lift = range.part.level.lift.to;

      for (let corner = range.first * 3; corner < (range.first + range.count) * 3; corner += 1) {
        const vertex = (indices[corner] ?? 0) * 3;

        box.expandByPoint(
          project.set(
            positions[vertex] ?? 0,
            (positions[vertex + 1] ?? 0) + lift,
            positions[vertex + 2] ?? 0,
          ),
        );
      }
    }

    return box;
  };

  const highlight = (element: number, strong: boolean, pinned: boolean): Highlight => {
    const list = (ranges.get(element) ?? []).filter((range) => range.part.presence === "normal");
    const room = rooms.get(element) ?? null;
    let total = 0;

    for (const range of list) {
      total += range.count;
    }

    const positions = new Float32Array(total * 9);
    let cursor = 0;

    for (const range of list) {
      const { indices, positions: source } = range.part.source;

      for (let corner = range.first * 3; corner < (range.first + range.count) * 3; corner += 1) {
        const vertex = (indices[corner] ?? 0) * 3;

        positions[cursor] = source[vertex] ?? 0;
        positions[cursor + 1] = (source[vertex + 1] ?? 0) + (room === null ? 0 : 0.004);
        positions[cursor + 2] = source[vertex + 2] ?? 0;
        cursor += 3;
      }
    }

    const level = list[0]?.part.level ?? levelOf(model.elements[element]?.storey ?? -1);
    const geometry = new BufferGeometry();

    geometry.setAttribute("position", new BufferAttribute(positions, 3));

    let opacity = strong ? 0.42 : 0.2;

    if (room !== null) {
      opacity = 0.35;
    }

    const material = new MeshBasicMaterial({
      clippingPlanes: [level.plane],
      color: accent,
      depthWrite: false,
      opacity,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
      side: DoubleSide,
      transparent: true,
    });

    const overlay = new Mesh(geometry, material);

    overlay.renderOrder = 4;
    level.group.add(overlay);

    let outline: LineSegments2 | null = null;
    let outlineGeometry: LineSegmentsGeometry | null = null;
    let outlineMaterial: LineMaterial | null = null;

    if (room !== null) {
      const edges = new EdgesGeometry(geometry, 28);

      outlineGeometry = new LineSegmentsGeometry().fromEdgesGeometry(edges).translate(0, 0.015, 0);
      edges.dispose();

      outlineMaterial = new LineMaterial({
        clippingPlanes: [level.plane],
        color: accent,
        depthTest: true,
        linewidth: 2.5,
      });

      outlineMaterial.resolution.set(width, height);
      lineMaterials.add(outlineMaterial);
      outline = new LineSegments2(outlineGeometry, outlineMaterial);
      outline.renderOrder = 5;
      level.group.add(outline);
    }

    let label: HTMLElement | null = null;

    if (pinned && room !== null) {
      label = document.createElement("span");
      label.className = "desk-chip-tag pointer-events-none absolute top-0 left-0";
      label.style.visibility = "hidden";
      label.textContent = roomText(model.elements[element], room.area);
      labels.append(label);
    }

    return {
      dispose: () => {
        level.group.remove(overlay);
        geometry.dispose();
        material.dispose();

        if (outline !== null && outlineGeometry !== null && outlineMaterial !== null) {
          level.group.remove(outline);
          outlineGeometry.dispose();
          outlineMaterial.dispose();
          lineMaterials.delete(outlineMaterial);
        }

        label?.remove();
      },
      element,
      label,
      room,
    };
  };

  const pinned = (element: number) =>
    selection?.element === element || marks.some((item) => item.element === element);

  const textOf = (element: number) => {
    const room = rooms.get(element);

    if (room !== undefined) {
      return roomText(model.elements[element], room.area);
    }

    return model.elements[element]?.label ?? null;
  };

  const setHover = (element: number) => {
    if (element === hovered) {
      return;
    }

    hovered = element;
    hover?.dispose();
    hover = null;

    if (element >= 0 && !pinned(element)) {
      hover = highlight(element, false, false);
    }

    canvas.style.cursor = element >= 0 ? "pointer" : "";
    events.onHover(element >= 0 && !pinned(element) ? textOf(element) : null);
    request();
  };

  const select = (element: number) => {
    selection?.dispose();
    selection = null;
    hover?.dispose();
    hover = null;
    hovered = -1;
    events.onHover(null);

    if (element >= 0) {
      selection = highlight(element, true, true);
    }

    request();
  };

  const clearMarks = () => {
    for (const item of marks) {
      item.dispose();
    }

    marks = [];
  };

  const partOf = (hit: Intersection) => parts.find((part) => part.mesh === hit.object);

  const pick = () => {
    raycaster.setFromCamera(pointer, camera);

    const targets: Mesh[] = [];

    for (const part of parts) {
      if (part.presence === "normal" && part.mesh.visible) {
        targets.push(part.mesh);
      }
    }

    for (const hit of raycaster.intersectObjects(targets, false)) {
      const part = partOf(hit);

      if (
        part !== undefined &&
        hit.faceIndex !== undefined &&
        hit.faceIndex !== null &&
        hit.point.y <= part.level.plane.constant + 0.001
      ) {
        return elementAt(part, hit.faceIndex);
      }
    }

    return -1;
  };

  const placeTag = (x: number, y: number) => {
    tag.style.transform = `translate(${String(Math.round(x + 14))}px, ${String(Math.round(y + 16))}px)`;
  };

  const pointAt = (event: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    pointer.set((x / rect.width) * 2 - 1, -(y / rect.height) * 2 + 1);

    return { x, y };
  };

  const onMove = (event: PointerEvent) => {
    if (event.buttons !== 0) {
      setHover(-1);

      return;
    }

    const at = pointAt(event);

    placeTag(at.x, at.y);

    if (pickFrame === 0) {
      pickFrame = requestAnimationFrame(() => {
        pickFrame = 0;
        setHover(pick());
      });
    }
  };

  const onLeave = () => {
    setHover(-1);
  };

  const onDown = (event: PointerEvent) => {
    down = { time: performance.now(), x: event.clientX, y: event.clientY };
  };

  const onUp = (event: PointerEvent) => {
    const start = down;

    down = null;

    if (start === null || event.button !== 0) {
      return;
    }

    const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);

    if (moved > 5 || performance.now() - start.time > 500) {
      return;
    }

    pointAt(event);

    const element = pick();

    select(element === selection?.element ? -1 : element);
  };

  const resize = () => {
    const nextWidth = canvasHost.clientWidth;
    const nextHeight = canvasHost.clientHeight;

    if (nextWidth === 0 || nextHeight === 0) {
      return;
    }

    width = nextWidth;
    height = nextHeight;
    freeRight = clamp(readPixels(canvasHost, "--desk-free-right"), 0, width * 0.6);
    freeBottom = clamp(readPixels(canvasHost, "--desk-free-bottom"), 0, height * 0.4);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.setViewOffset(width, height, freeRight / 2, (freeBottom - topInset) / 2, width, height);
    camera.updateProjectionMatrix();

    for (const material of lineMaterials) {
      material.resolution.set(width, height);
    }

    request();
  };

  const setControls = () => {
    const plan = view === "plan";

    controls.enableRotate = !plan;
    controls.mouseButtons = {
      LEFT: plan ? MOUSE.PAN : MOUSE.ROTATE,
      MIDDLE: MOUSE.DOLLY,
      RIGHT: MOUSE.PAN,
    };
  };

  const emit = () => {
    events.onState({ furniture, storey, view });
  };

  const change = (nextView: ViewMode, nextStorey: number) => {
    view = nextView;
    storey = nextStorey;
    setHover(-1);
    select(-1);
    clearMarks();
    setControls();
    applyLayers(performance.now());

    const next = homePose();

    limitsFor(next);
    animateTo(next);
    emit();
  };

  const observer = new ResizeObserver(resize);

  observer.observe(canvasHost);
  resize();
  controls.addEventListener("change", request);
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerleave", onLeave);
  canvas.addEventListener("pointerdown", onDown);
  canvas.addEventListener("pointerup", onUp);
  setControls();
  applyLayers(performance.now());

  const home = homePose();

  limitsFor(home);
  placeCamera({ ...home, radius: home.radius * 1.25, theta: home.theta - 0.5 });
  animateTo(home, 1300, easeOut);
  emit();

  return {
    clear: () => {
      select(-1);
      clearMarks();
    },
    dispose: () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(pickFrame);
      observer.disconnect();
      controls.removeEventListener("change", request);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointerup", onUp);
      controls.dispose();
      hover?.dispose();
      selection?.dispose();
      clearMarks();

      for (const item of disposables) {
        item.dispose();
      }

      renderer.dispose();
      canvas.remove();
    },
    frame: () => {
      const chosen = [selection, ...marks].filter((item) => item !== null);
      const box = new Box3();

      for (const item of chosen) {
        box.union(rangeBox(item.element));
      }

      if (box.isEmpty()) {
        animateTo(homePose());

        return;
      }

      box.expandByScalar(1.2);
      animateTo(poseFor(box, anglesOf(view)));
    },
    mark: (names: readonly string[]) => {
      const found = [...rooms.keys()].filter((element) => {
        const record = model.elements[element];

        return record !== undefined && matchesRoom(record, names);
      });

      const first = model.elements[found[0] ?? -1]?.storey;

      if (first !== undefined && view !== "exploded" && view !== "building" && first !== storey) {
        storey = first;
        applyLayers(performance.now());
        emit();
      }

      select(-1);
      clearMarks();

      marks = found.flatMap((element) =>
        view === "exploded" || model.elements[element]?.storey === storey
          ? [highlight(element, true, true)]
          : [],
      );

      const box = new Box3();

      for (const element of found) {
        box.union(rangeBox(element));
      }

      if (!box.isEmpty()) {
        box.expandByScalar(1.5);
        animateTo(poseFor(box, anglesOf(view)));
      }

      request();
    },
    reset: () => {
      furniture = false;
      change("cutaway", defaultStorey);
    },
    setFurniture: (on: boolean) => {
      furniture = on;
      applyLayers(performance.now());
      request();
      emit();
    },
    setStorey: (next: number) => {
      change(view === "building" ? "cutaway" : view, next);
    },
    setView: (next: ViewMode) => {
      change(next, storey);
    },
    shownStoreys,
    zoom: (factor: number) => {
      const pose = currentPose();

      animateTo({ ...pose, radius: pose.radius / factor }, 360);
    },
  };
};
