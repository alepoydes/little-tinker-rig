"""LDraw/MPD to shared part meshes, instances and explicit assembly steps.

Coordinates remain in LDU (-Y is up). Geometry is double-sided: BFC winding
cannot make a mirrored or uncertified part disappear. No connection inference
or physical simulation is performed.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from .ldraw_parts import PartLibrary, read_file
from .paths import resource


def box_corners(bounds):
    return np.array(
        [
            [bounds[x, 0], bounds[y, 1], bounds[z, 2]]
            for x in (0, 1)
            for y in (0, 1)
            for z in (0, 1)
        ]
    )


@dataclass(frozen=True)
class Mesh:
    title: str
    triangles: np.ndarray  # (n, 3, 3)
    colors: np.ndarray  # one LDraw color code per triangle
    lines: np.ndarray  # (n, 4, 3); controls coincide for unconditional edges
    line_colors: np.ndarray

    @cached_property
    def bounds(self):
        points = np.concatenate(
            (self.triangles.reshape(-1, 3), self.lines[:, :2].reshape(-1, 3))
        )
        return (
            np.array([points.min(axis=0), points.max(axis=0)])
            if len(points)
            else np.zeros((2, 3))
        )


@dataclass(frozen=True)
class Instance:
    identity: str
    part: str
    color: int
    transform: np.ndarray
    step: int
    groups: tuple[str, ...]


@dataclass(frozen=True)
class Scene:
    meshes: dict[str, Mesh]
    instances: tuple[Instance, ...]
    colors: dict[int, tuple]
    step_count: int

    def corners(self, instances=None):
        points = []
        for item in self.instances if instances is None else instances:
            corners = box_corners(self.meshes[item.part].bounds)
            points.append(corners @ item.transform[:3, :3].T + item.transform[:3, 3])
        return np.array(points).reshape(-1, 8, 3)

    def bounds(self, instances=None):
        points = self.corners(instances).reshape(-1, 3)
        return (
            np.array([np.min(points, axis=0), np.max(points, axis=0)])
            if len(points)
            else np.array([[-1.0, -1.0, -1.0], [1.0, 1.0, 1.0]])
        )


def color_code(value):
    return int(value, 16) if value.lower().startswith("0x") else int(value)


def rgba(code, colors, inherited=7, edge=False):
    if code in (16, 24):
        edge = code == 24 or edge
        code = inherited
    if code & 0xFF000000 == 0x02000000:
        rgb = tuple(((code >> shift) & 255) / 255 for shift in (16, 8, 0))
        return (*rgb, 1.0) if not edge else (0.12, 0.14, 0.17, 1.0)
    face, outline = colors.get(code, ((0.65, 0.67, 0.7, 1.0), (0.15, 0.16, 0.18, 1.0)))
    return outline if edge else face


def reference(tokens):
    if len(tokens) < 15:
        raise ValueError("Incomplete LDraw reference")
    values = np.array([float(v) for v in tokens[2:14]], dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite LDraw transform")
    transform = np.eye(4)
    transform[:3, 3] = values[:3]
    transform[:3, :3] = values[3:].reshape(3, 3)
    return (
        color_code(tokens[1]),
        transform,
        " ".join(tokens[14:]).replace("\\", "/").lower(),
    )


class LDraw(AbstractContextManager):
    def __init__(self, path: Path, library: Path | None = None):
        path = path.resolve()
        self.root = path.parent
        self.dependencies = {}
        self.files = {}
        self.parts = set()
        self.meshes = {}
        self.colors = {}
        self.loading = set()
        data = read_file(path, self.dependencies)
        if data is None:
            raise FileNotFoundError(path)
        self.main = self.add_file(path.name, data.decode("utf-8-sig"))
        self.library = PartLibrary(library or self.root, dependencies=self.dependencies)
        self.local = (
            self.library
            if self.library.path == self.root
            else PartLibrary(self.root, dependencies=self.dependencies)
        )
        try:
            if config := self.library.read("LDConfig.ldr"):
                self.add_file("ldconfig.ldr", config.decode("utf-8-sig"))
        except Exception:
            if self.local is not self.library:
                self.local.close()
            self.library.close()
            raise

    def __exit__(self, *args):
        if self.local is not self.library:
            self.local.close()
        self.library.close()

    def add_file(self, name, text):
        current = name.lower()
        first = None
        records = []
        lines = text.splitlines()
        # MPD content before the first FILE or !DATA marker is outside any file.
        active = not any(
            line.split(maxsplit=2)[:2] in (["0", "FILE"], ["0", "!DATA"])
            for line in lines
        )
        embedded = False
        for line in lines:
            tokens = line.split()
            if not tokens:
                continue
            if tokens[:2] == ["0", "FILE"]:
                if active and (records or embedded):
                    self.files[current] = records
                current = " ".join(tokens[2:]).replace("\\", "/").lower()
                resource(self.root, current)
                first = first or current
                records = []
                active = embedded = True
            elif tokens[:2] == ["0", "NOFILE"]:
                if active:
                    self.files[current] = records
                records = []
                active = False
            elif tokens[:2] == ["0", "!DATA"]:
                if active and (records or embedded):
                    self.files[current] = records
                records = []
                active = False
            else:
                if not active:
                    continue
                records.append(tokens)
                # Flexible components carry ordinary LDraw fallback geometry.
                # Their segments belong to one physical component, not a sequence
                # of subassembly steps or thousands of selectable cable slices.
                if tokens[:3] == ["0", "!LDCAD", "CONTENT"] and any(
                    value in tokens[3:] for value in ("[type=path]", "[type=spring]")
                ):
                    self.parts.add(current)
                if tokens[:3] == ["0", "UNOFFICIAL", "PART"]:
                    self.parts.add(current)
                if tokens[:2] == ["0", "!COLOUR"]:

                    def field(key, default, tokens=tokens):
                        return (
                            tokens[tokens.index(key) + 1] if key in tokens else default
                        )

                    def rgb(value):
                        number = int(value.lstrip("#"), 16)
                        return tuple(((number >> n) & 255) / 255 for n in (16, 8, 0))

                    code = int(field("CODE", "7"))
                    edge = field("EDGE", "#333333")
                    edge_color = (
                        (*rgb(edge), 1.0)
                        if edge.startswith("#")
                        else rgba(int(edge), self.colors)
                    )
                    self.colors[code] = (
                        (
                            *rgb(field("VALUE", "#AAAAAA")),
                            int(field("ALPHA", "255")) / 255,
                        ),
                        edge_color,
                    )
        if active and (records or embedded or first is None):
            self.files[current] = records
        return first or name.lower()

    def records(self, name):
        if name not in self.files:
            data = self.local.read(name)
            if data is None:
                for prefix in ("parts/", "p/", ""):
                    data = self.library.read(prefix + name)
                    if data is not None:
                        break
            if data is None:
                raise ValueError(f"Missing LDraw part: {name}")
            self.add_file(name, data.decode("utf-8-sig"))
        return self.files[name]

    def mesh(self, name):
        if name in self.meshes:
            return self.meshes[name]
        if name in self.loading:
            raise ValueError(f"Circular LDraw reference: {name}")
        self.loading.add(name)
        triangles, colors, lines, line_colors = [], [], [], []
        records = self.records(name)
        try:
            for tokens in records:
                kind = tokens[0]
                if kind == "1":
                    color, matrix, child = reference(tokens)
                    mesh = self.mesh(child)
                    triangles.extend(mesh.triangles @ matrix[:3, :3].T + matrix[:3, 3])
                    colors.extend(np.where(mesh.colors == 16, color, mesh.colors))
                    lines.extend(mesh.lines @ matrix[:3, :3].T + matrix[:3, 3])
                    # Retain an explicit edge color when a differently colored
                    # subpart is flattened into a shared mesh.
                    line_colors.extend(
                        np.where(
                            mesh.line_colors == 24,
                            -color - 1 if color != 16 else 24,
                            np.where(mesh.line_colors == 16, color, mesh.line_colors),
                        )
                    )
                elif kind in {"2", "3", "4", "5"}:
                    count = {"2": 2, "3": 3, "4": 4, "5": 4}[kind]
                    if len(tokens) != 2 + count * 3:
                        raise ValueError(f"Invalid LDraw primitive in {name}")
                    points = np.array(tokens[2:], dtype=np.float32).reshape(count, 3)
                    if not np.isfinite(points).all():
                        raise ValueError("Non-finite LDraw vertices")
                    color = color_code(tokens[1])
                    if kind in {"3", "4"}:
                        triangles.append(points[:3])
                        colors.append(color)
                        if kind == "4":
                            triangles.append(points[[0, 2, 3]])
                            colors.append(color)
                    else:
                        lines.append(points if kind == "5" else points[[0, 1, 0, 0]])
                        line_colors.append(color)
            mesh = Mesh(
                " ".join(records[0][1:]) if records and records[0][0] == "0" else name,
                np.array(triangles, dtype=np.float32).reshape(-1, 3, 3),
                np.array(colors, dtype=np.int64),
                np.array(lines, dtype=np.float32).reshape(-1, 4, 3),
                np.array(line_colors, dtype=np.int64),
            )
            self.meshes[name] = mesh
            return mesh
        finally:
            self.loading.remove(name)

    def scene(self):
        instances = []
        used = set()
        stack = set()
        step = 0
        pending = False

        def assembly_records(name):
            # Inline geometry (for example, a flexible cable) is a shared mesh
            # in its own right. Preserve its position among references and steps.
            primitives = []
            number = 0
            for tokens in [*self.records(name), ["0", "END"]]:
                if tokens[0] in {"2", "3", "4", "5"}:
                    primitives.append(tokens)
                    continue
                if primitives and (
                    tokens[0] == "1"
                    or tokens[:2] in (["0", "STEP"], ["0", "ROTSTEP"], ["0", "END"])
                    or tokens[:3]
                    in (
                        ["0", "!LITTLE_TINKER_RIG", "ID"],
                        ["0", "!PYBLOCKS", "ID"],
                    )
                ):
                    number += 1
                    part = f"{name}/geometry-{number}.dat"
                    self.files[part] = primitives
                    primitives = []
                    yield "1 16 0 0 0 1 0 0 0 1 0 0 0 1".split() + [part]
                yield tokens

        def visit(name, transform, inherited, groups):
            nonlocal step, pending
            if name in stack:
                raise ValueError(f"Circular LDraw model: {name}")
            stack.add(name)
            number = 0
            identity = None
            for tokens in assembly_records(name):
                if tokens[:3] in (
                    ["0", "!LITTLE_TINKER_RIG", "ID"],
                    ["0", "!PYBLOCKS", "ID"],
                ):
                    identity = " ".join(tokens[3:])
                    if not identity or "/" in identity:
                        raise ValueError(
                            "An instance id must be nonempty and cannot contain /"
                        )
                elif tokens[:2] in (["0", "STEP"], ["0", "ROTSTEP"]):
                    pending = bool(instances)
                elif tokens[0] == "1":
                    number += 1
                    color, matrix, child = reference(tokens)
                    color = inherited if color == 16 else color
                    key = "/".join((*groups, identity or str(number)))
                    identity = None
                    if key in used:
                        raise ValueError(f"Duplicate instance id: {key}")
                    used.add(key)
                    matrix = transform @ matrix
                    self.records(child)
                    if child.endswith(".dat") or child in self.parts:
                        self.mesh(child)
                        if pending:
                            step += 1
                            pending = False
                        instances.append(
                            Instance(key, child, color, matrix, step, groups)
                        )
                    else:
                        visit(child, matrix, color, (*groups, key.rsplit("/", 1)[-1]))
            stack.remove(name)

        if not self.main.endswith(".dat") and self.main not in self.parts:
            visit(self.main, np.eye(4), 7, ())
        if not instances:
            # A standalone part is useful while authoring instructions.
            self.mesh(self.main)
            instances.append(Instance("part", self.main, 7, np.eye(4), 0, ()))
        meshes = {item.part: self.meshes[item.part] for item in instances}
        return Scene(meshes, tuple(instances), self.colors, step + 1)
