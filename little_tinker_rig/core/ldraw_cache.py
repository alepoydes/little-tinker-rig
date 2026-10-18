"""Disposable, portable scene caches: JSON metadata and numeric NumPy arrays."""

import hashlib
import json
import math
import tempfile
from pathlib import Path
from zipfile import BadZipFile

import numpy as np

from .ldraw import Instance, LDraw, Mesh, Scene
from .ldraw_parts import check_cancelled, digest, directory_fingerprint, read_file
from .paths import parts_cache, resource

FORMAT = 1
# Geometry changes invalidate caches even in development builds of the same version.
CONVERTER = hashlib.sha256(
    b"".join(
        Path(__file__).with_name(name).read_bytes()
        for name in ("ldraw.py", "ldraw_parts.py")
    )
).hexdigest()


def _decode(archive, data):
    if not isinstance(data, dict):
        raise ValueError("Invalid cached metadata")

    def number(value):
        try:
            return type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            return False

    if type(data.get("steps")) is not int or not 0 < data["steps"] <= 2**31 - 1:
        raise ValueError("Invalid cached steps")
    meshes_data = data.get("meshes")
    if not isinstance(meshes_data, list) or any(
        not isinstance(item, list)
        or len(item) != 2
        or not all(isinstance(value, str) for value in item)
        for item in meshes_data
    ):
        raise ValueError("Invalid cached meshes")
    instances_data = data.get("instances")
    if not isinstance(instances_data, list) or any(
        not isinstance(item, list)
        or len(item) != 5
        or not isinstance(item[0], str)
        or not isinstance(item[1], str)
        or type(item[2]) is not int
        or type(item[3]) is not int
        or not isinstance(item[4], list)
        or not all(isinstance(group, str) for group in item[4])
        for item in instances_data
    ):
        raise ValueError("Invalid cached instances")
    colors_data = data.get("colors")
    if not isinstance(colors_data, dict) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(
            not isinstance(color, list)
            or len(color) != 4
            or not all(number(channel) for channel in color)
            for color in pair
        )
        for pair in colors_data.values()
    ):
        raise ValueError("Invalid cached colors")

    def array(name, dtype, shape):
        value = archive[name]
        if value.dtype != np.dtype(dtype) or value.shape[1:] != shape:
            raise ValueError("Invalid cached geometry")
        if not np.isfinite(value).all():
            raise ValueError("Non-finite cached geometry")
        return value

    meshes = {}
    for index, (name, title) in enumerate(meshes_data):
        triangles = array(f"{index}_triangles", "float32", (3, 3))
        colors = array(f"{index}_colors", "int64", ())
        lines = array(f"{index}_lines", "float32", (4, 3))
        line_colors = array(f"{index}_line_colors", "int64", ())
        if len(triangles) != len(colors) or len(lines) != len(line_colors):
            raise ValueError("Invalid cached colors")
        meshes[name] = Mesh(title, triangles, colors, lines, line_colors)
    transforms = array("transforms", "float64", (4, 4))
    instances = tuple(
        Instance(identity, part, color, transform, step, tuple(groups))
        for (identity, part, color, step, groups), transform in zip(
            instances_data, transforms, strict=True
        )
    )
    if not instances or any(
        i.part not in meshes or not 0 <= i.step < data["steps"] for i in instances
    ):
        raise ValueError("Invalid cached instances")
    colors = {
        int(code): (tuple(face), tuple(edge))
        for code, (face, edge) in colors_data.items()
    }
    return Scene(meshes, instances, colors, data["steps"])


def _store(path, scene, dependencies, cancelled):
    data = {
        "dependencies": dependencies,
        "meshes": [(name, mesh.title) for name, mesh in scene.meshes.items()],
        "instances": [
            (i.identity, i.part, i.color, i.step, i.groups) for i in scene.instances
        ],
        "colors": scene.colors,
        "steps": scene.step_count,
    }
    arrays = {
        "metadata": np.frombuffer(json.dumps(data).encode("utf-8"), dtype=np.uint8),
        "transforms": np.array([i.transform for i in scene.instances]),
    }
    for index, mesh in enumerate(scene.meshes.values()):
        for field in ("triangles", "colors", "lines", "line_colors"):
            arrays[f"{index}_{field}"] = getattr(mesh, field)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            # Uncompressed arrays trade disposable disk space for fast startup.
            np.savez(stream, **arrays)
        check_cancelled(cancelled)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def load_scene(path, library, *, library_digest=None, cancelled=None):
    """Reuse geometry across launches and lesson copies; validate local dependencies.

    A supplied library digest must come from resolve_library's verified archive.
    Missing local lookup candidates are dependencies too: adding an override must
    invalidate a model that previously used an archive or a lower-priority file.
    """
    path, library = Path(path).resolve(), Path(library).resolve()
    check_cancelled(cancelled)
    library_key = (
        library_digest or digest(library)
        if library.is_file()
        else "directory:"
        + str(
            library.relative_to(path.parent)
            if library.is_relative_to(path.parent)
            else library
        )
    )
    key = json.dumps((FORMAT, CONVERTER, path.name, digest(path), library_key))
    destination = (
        parts_cache() / "scenes" / (hashlib.sha256(key.encode()).hexdigest() + ".npz")
    )
    roots = {"model": path.parent, "library": library}
    try:
        with np.load(destination, allow_pickle=False) as archive:
            data = json.loads(archive["metadata"].tobytes())
            current = {}
            for root, name, expected in data["dependencies"]:
                check_cancelled(cancelled)
                dependency = resource(roots[root], name)
                if isinstance(expected, str) and expected.startswith("directory:"):
                    actual = directory_fingerprint(dependency)
                else:
                    read_file(dependency, current)
                    actual = current[dependency]
                if actual != expected:
                    break
            else:
                scene = _decode(archive, data)
                check_cancelled(cancelled)
                return scene
    except (OSError, ValueError, KeyError, TypeError, EOFError, BadZipFile):
        # The source model remains authoritative; damaged caches are replaceable.
        pass
    check_cancelled(cancelled)
    with LDraw(path, library) as reader:
        scene = reader.scene()
        dependencies = []
        for dependency, checksum in reader.dependencies.items():
            root = "model" if dependency.is_relative_to(path.parent) else "library"
            dependencies.append(
                (root, dependency.relative_to(roots[root]).as_posix(), checksum)
            )
    check_cancelled(cancelled)
    try:
        _store(destination, scene, dependencies, cancelled)
    except OSError:
        # A read-only or full cache must not prevent opening a valid model.
        pass
    return scene
