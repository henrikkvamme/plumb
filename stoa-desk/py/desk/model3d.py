"""Tessellate an IFC model for the 3D view of the desk.

`mesh(path)` returns one binary payload: a little-endian uint32 with the length of a JSON header, the header padded to
4 bytes, then the arrays. The header lists the storeys, the elements (a plain label each) and the meshes. One mesh holds
the triangles of one group on one storey, so the view needs few draw calls. Each mesh has `spans`: triples of element
index, first triangle and triangle count, so a click on a triangle finds its element. Positions are metres, Y up, with
the model centred on X and Z and its lowest point at Y 0.
"""

from __future__ import annotations

import json
import struct
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
from ifcopenshell import entity_instance

THREADS = 2
GLASS_TRANSPARENCY = 0.2
GROUPS = {
    "IfcWall": "wall", "IfcWallStandardCase": "wall", "IfcCurtainWall": "wall", "IfcPlate": "wall",
    "IfcSlab": "slab", "IfcCovering": "slab", "IfcFooting": "slab",
    "IfcRoof": "roof",
    "IfcWindow": "window",
    "IfcDoor": "door",
    "IfcStair": "stair", "IfcStairFlight": "stair", "IfcRamp": "stair", "IfcRampFlight": "stair", "IfcRailing": "stair",
    "IfcColumn": "column",
    "IfcBeam": "beam", "IfcMember": "beam",
    "IfcFurnishingElement": "furniture", "IfcFurniture": "furniture", "IfcSystemFurnitureElement": "furniture",
    "IfcSpace": "space",
}  # fmt: skip
LABELS = {
    "IfcWall": "Wall", "IfcWallStandardCase": "Wall", "IfcCurtainWall": "Curtain wall", "IfcPlate": "Panel",
    "IfcSlab": "Floor slab", "IfcFooting": "Footing", "IfcRoof": "Roof", "IfcStair": "Stair",
    "IfcStairFlight": "Stair", "IfcRamp": "Ramp", "IfcRampFlight": "Ramp", "IfcRailing": "Railing",
    "IfcColumn": "Column", "IfcBeam": "Beam", "IfcMember": "Frame member", "IfcFurnishingElement": "Furniture",
    "IfcFurniture": "Furniture", "IfcSystemFurnitureElement": "Furniture", "IfcBuildingElementProxy": "Part",
}  # fmt: skip
COVERINGS = {"CEILING": "Ceiling", "FLOORING": "Floor finish", "CLADDING": "Cladding", "ROOFING": "Roofing"}

_cache: dict[str, bytes] = {}
_lock = threading.Lock()
_building: dict[str, threading.Lock] = defaultdict(threading.Lock)


@dataclass
class _Mesh:
    group: str
    storey: int
    positions: list[np.ndarray] = field(default_factory=list)
    indices: list[np.ndarray] = field(default_factory=list)
    spans: list[tuple[int, int, int]] = field(default_factory=list)
    vertices: int = 0
    triangles: int = 0

    def add(self, element: int, verts: np.ndarray, faces: np.ndarray) -> None:
        used, remap = np.unique(faces, return_inverse=True)
        self.positions.append(verts[used])
        self.indices.append(remap.reshape(-1, 3).astype(np.uint32) + self.vertices)
        self.spans.append((element, self.triangles, len(faces)))
        self.vertices += len(used)
        self.triangles += len(faces)


def _metres(value: object, scale: float) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return f"{float(value) * scale:.2f}".rstrip("0").rstrip(".") + " m"


def _text(value: object) -> str:
    return str(value).strip() if value else ""


def _label(element: entity_instance, scale: float) -> str:
    kind = element.is_a()
    if kind == "IfcSpace":
        name, long = _text(element.Name), _text(element.LongName)
        if name and long and long != name:
            return f"Room {name} · {long}"
        return f"Room {name or long}".strip()
    if kind in {"IfcDoor", "IfcWindow"}:
        width = _metres(getattr(element, "OverallWidth", None), scale)
        word = "Door" if kind == "IfcDoor" else "Window"
        return f"{word} {width}" if width else word
    if kind == "IfcCovering":
        return COVERINGS.get(str(getattr(element, "PredefinedType", "") or ""), "Covering")
    if kind == "IfcSlab" and str(getattr(element, "PredefinedType", "")) == "ROOF":
        return "Roof"
    return LABELS.get(kind, "Part")


def _parent(element: entity_instance) -> entity_instance | None:
    return ifcopenshell.util.element.get_container(element) or ifcopenshell.util.element.get_aggregate(element)


def _storey(element: entity_instance, ids: dict[int, int]) -> int:
    current = _parent(element)
    for _ in range(8):
        if current is None:
            return -1
        if current.id() in ids:
            return ids[current.id()]
        current = _parent(current)
    return -1


def _in_roof(element: entity_instance) -> bool:
    parent = ifcopenshell.util.element.get_aggregate(element)
    return parent is not None and parent.is_a("IfcRoof")


def _group(element: entity_instance) -> str:
    kind = element.is_a()
    if kind == "IfcSlab" and (str(getattr(element, "PredefinedType", "")) == "ROOF" or _in_roof(element)):
        return "roof"
    if kind == "IfcCovering" and str(getattr(element, "PredefinedType", "")) == "ROOFING":
        return "roof"
    return GROUPS.get(kind, "other")


def _storeys(model: ifcopenshell.file, scale: float) -> list[tuple[entity_instance, str, float]]:
    found = []
    for storey in model.by_type("IfcBuildingStorey"):
        try:
            elevation = float(ifcopenshell.util.placement.get_local_placement(storey.ObjectPlacement)[2][3]) * scale
        except Exception:
            elevation = float(storey.Elevation or 0.0) * scale
        found.append((storey, _text(storey.Name) or _text(storey.LongName) or "Storey", elevation))
    return sorted(found, key=lambda item: item[2])


def _glass(geometry: Any) -> np.ndarray | None:  # noqa: ANN401 - the iterator geometry has no stubs
    materials = geometry.materials
    if not materials:
        return None
    clear = np.array([float(getattr(m, "transparency", 0.0) or 0.0) > GLASS_TRANSPARENCY for m in materials])
    if not clear.any():
        return None
    ids = np.frombuffer(geometry.material_ids_buffer, dtype=np.int32)
    return np.where(ids >= 0, clear[np.clip(ids, 0, len(clear) - 1)], False)


def _consistent(faces: np.ndarray) -> bool:
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]).astype(np.int64)
    keys = edges[:, 0] * (int(faces.max()) + 1) + edges[:, 1]
    return len(np.unique(keys)) == len(keys)


def _orient(faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    owners: dict[tuple[int, int], list[int]] = defaultdict(list)
    rows = faces.tolist()
    for index, (a, b, c) in enumerate(rows):
        for u, v in ((a, b), (b, c), (c, a)):
            owners[(min(u, v), max(u, v))].append(index)
    group = np.full(len(rows), -1)
    for seed in range(len(rows)):
        if group[seed] >= 0:
            continue
        group[seed] = seed
        queue = deque([seed])
        while queue:
            a, b, c = rows[queue.popleft()]
            for u, v in ((a, b), (b, c), (c, a)):
                for other in owners[(min(u, v), max(u, v))]:
                    if group[other] >= 0:
                        continue
                    x, y, z = rows[other]
                    if (u, v) in ((x, y), (y, z), (z, x)):
                        rows[other] = [x, z, y]
                    group[other] = seed
                    queue.append(other)
    return np.array(rows, dtype=faces.dtype), group


def _outward(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    group = np.zeros(len(faces), dtype=np.int64)
    if not _consistent(faces):
        faces, group = _orient(faces)
    corners = verts[faces] - verts[faces].reshape(-1, 3).mean(axis=0)
    volumes = np.einsum("ij,ij->i", corners[:, 0], np.cross(corners[:, 1], corners[:, 2]))
    keys, inverse = np.unique(group, return_inverse=True)
    sums = np.zeros(len(keys))
    np.add.at(sums, inverse, volumes)
    flip = sums[inverse] < 0
    return np.where(flip[:, None], faces[:, [0, 2, 1]], faces)


def _room(space: entity_instance, area_scale: float) -> dict[str, Any]:
    found: dict[str, Any] = {"name": _text(space.Name), "long": _text(space.LongName)}
    sets = ifcopenshell.util.element.get_psets(space, qtos_only=True)
    for key in ("NetFloorArea", "GrossFloorArea"):
        for values in sets.values():
            value = values.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
                return found | {"area": round(float(value) * area_scale, 2)}
    return found


def _build(path: Path) -> bytes:  # noqa: PLR0915 - one pass over the iterator
    started = time.perf_counter()
    model = ifcopenshell.open(str(path))
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    area_scale = ifcopenshell.util.unit.calculate_unit_scale(model, "AREAUNIT")
    storeys = _storeys(model, scale)
    storey_ids = {storey.id(): index for index, (storey, _, _) in enumerate(storeys)}
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    iterator = ifcopenshell.geom.iterator(settings, model, THREADS, exclude=model.by_type("IfcOpeningElement"))
    meshes: dict[tuple[str, int], _Mesh] = {}
    elements: list[dict[str, Any]] = []
    if iterator.initialize():
        while True:
            shape = iterator.get()
            geometry = shape.geometry
            faces = np.frombuffer(geometry.faces_buffer, dtype=np.int32).reshape(-1, 3)
            if len(faces):
                verts = np.frombuffer(geometry.verts_buffer, dtype=np.float64).reshape(-1, 3)
                faces = _outward(verts, faces)
                element = model.by_id(shape.id)
                group = _group(element)
                storey = _storey(element, storey_ids)
                index = len(elements)
                record = {"id": shape.id, "label": _label(element, scale), "group": group, "storey": storey}
                if group == "space":
                    record |= _room(element, area_scale)
                elements.append(record)
                glass = _glass(geometry) if group not in {"space", "furniture"} else None
                parts = [(group, faces)] if glass is None else [(group, faces[~glass]), ("glass", faces[glass])]
                for part, chosen in parts:
                    if len(chosen):
                        key = (part, storey)
                        if key not in meshes:
                            meshes[key] = _Mesh(part, storey)
                        meshes[key].add(index, verts, chosen)
            if not iterator.next():
                break
    solid = [m for m in meshes.values() if m.group != "space"] or list(meshes.values())
    if not solid:
        message = "The model has no geometry to show."
        raise ValueError(message)
    every = np.concatenate([p for m in solid for p in m.positions])
    low, high = every.min(axis=0), every.max(axis=0)
    centre = np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])
    header_meshes: list[dict[str, Any]] = []
    chunks: list[bytes] = []
    offset = 0

    def put(array: np.ndarray) -> dict[str, int]:
        nonlocal offset
        data = array.tobytes()
        chunks.append(data)
        entry = {"offset": offset, "length": int(array.size)}
        offset += len(data)
        return entry

    for mesh in sorted(meshes.values(), key=lambda m: (m.group, m.storey)):
        local = np.concatenate(mesh.positions) - centre
        yup = np.stack([local[:, 0], local[:, 2], -local[:, 1]], axis=1).astype(np.float32)
        header_meshes.append({
            "group": mesh.group,
            "storey": mesh.storey,
            "positions": put(yup),
            "indices": put(np.concatenate(mesh.indices)),
            "spans": put(np.array(mesh.spans, dtype=np.uint32)),
        })  # fmt: skip
    size = high - low
    header = {
        "storeys": [{"name": name, "elevation": round(elevation - float(centre[2]), 3)} for _, name, elevation in storeys],
        "elements": elements,
        "meshes": header_meshes,
        "size": [round(float(size[0]), 3), round(float(size[2]), 3), round(float(size[1]), 3)],
        "buildMs": round((time.perf_counter() - started) * 1000.0),
    }  # fmt: skip
    text = json.dumps(header, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    return struct.pack("<I", len(text)) + text + b"".join(chunks)


def is_model(path: Path) -> bool:
    return path.suffix.lower() == ".ifc"


def mesh(path: Path) -> bytes:
    key = str(path.resolve())
    with _lock:
        found = _cache.get(key)
        gate = _building[key]
    if found is not None:
        return found
    with gate:
        with _lock:
            found = _cache.get(key)
        if found is None:
            found = _build(path)
            with _lock:
                _cache[key] = found
    return found



TONES = {"glass": (0.78, 0.85, 0.9), "slab": (0.86, 0.85, 0.83), "roof": (0.8, 0.79, 0.77)}
WALL = (0.97, 0.96, 0.94)
PAPER = (232, 231, 227)
LIGHT = np.array([0.35, 0.85, 0.4])
OVERSAMPLE = 3


def picture(path: Path, width: int = 420, height: int = 280) -> bytes:
    """A small picture of the model from above at an angle, for the list of drawings."""
    import io  # noqa: PLC0415

    from PIL import Image, ImageDraw  # noqa: PLC0415

    payload = mesh(path)
    length = struct.unpack("<I", payload[:4])[0]
    meta = json.loads(payload[4 : 4 + length])
    body = payload[4 + length :]
    triangles: list[np.ndarray] = []
    colours: list[np.ndarray] = []
    for part in meta["meshes"]:
        if part["group"] in {"space", "furniture"}:
            continue
        positions = np.frombuffer(body, np.float32, part["positions"]["length"], part["positions"]["offset"]).reshape(-1, 3)
        indices = np.frombuffer(body, np.uint32, part["indices"]["length"], part["indices"]["offset"]).reshape(-1, 3)
        found = positions[indices]
        triangles.append(found)
        colours.append(np.tile(np.array(TONES.get(part["group"], WALL)), (len(found), 1)))
    every = np.concatenate(triangles).astype(np.float64)
    tone = np.concatenate(colours)
    turn, pitch = np.radians(-38.0), np.radians(34.0)
    x = every[..., 0] * np.cos(turn) - every[..., 2] * np.sin(turn)
    z = every[..., 0] * np.sin(turn) + every[..., 2] * np.cos(turn)
    y = every[..., 1]
    across, up, depth = x, y * np.cos(pitch) - z * np.sin(pitch), y * np.sin(pitch) + z * np.cos(pitch)
    normal = np.cross(every[:, 1] - every[:, 0], every[:, 2] - every[:, 0])
    size = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = normal / np.where(size == 0, 1, size)
    shade = 0.62 + 0.38 * np.abs(normal @ (LIGHT / np.linalg.norm(LIGHT)))
    big = (width * OVERSAMPLE, height * OVERSAMPLE)
    span = max((across.max() - across.min()) / big[0], (up.max() - up.min()) / big[1]) / 0.84
    px = (across - (across.max() + across.min()) / 2) / span + big[0] / 2
    py = big[1] / 2 - (up - (up.max() + up.min()) / 2) / span
    image = Image.new("RGB", big, PAPER)
    draw = ImageDraw.Draw(image)
    for i in np.argsort(depth.mean(axis=1)):
        fill = tuple(int(v) for v in np.clip(tone[i] * shade[i] * 255, 0, 255))
        draw.polygon([(float(px[i, k]), float(py[i, k])) for k in range(3)], fill=fill)
    out = io.BytesIO()
    image.resize((width, height), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:]:
        began = time.perf_counter()
        payload = mesh(Path(name))
        length = struct.unpack("<I", payload[:4])[0]
        meta = json.loads(payload[4 : 4 + length])
        triangles = sum(m["indices"]["length"] // 3 for m in meta["meshes"])
        print(f"{Path(name).name}: {len(payload) / 1e6:.2f} MB, {len(meta['meshes'])} meshes, {triangles} triangles, "
              f"{len(meta['elements'])} elements, {len(meta['storeys'])} storeys, {time.perf_counter() - began:.2f} s")  # fmt: skip
