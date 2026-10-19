import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import CancelledError
from pathlib import Path
from zipfile import ZipFile

import pytest

np = pytest.importorskip("numpy")

from little_tinker_rig.core import ldraw_cache  # noqa: E402
from little_tinker_rig.core.ldraw import LDraw  # noqa: E402
from little_tinker_rig.core.ldraw_cache import load_scene  # noqa: E402
from little_tinker_rig.core.paths import parts_cache  # noqa: E402


def part(length):
    return f"0 Sample part\n3 16 0 0 0 {length} 0 0 0 -20 0\n2 24 0 0 0 {length} 0 0\n"


@pytest.fixture
def model(tmp_path):
    root = tmp_path / "model"
    root.mkdir()
    path = root / "robot.mpd"
    path.write_text("""0 FILE main.ldr
1 4 10 0 0 1 0 0 0 1 0 0 0 1 part.dat
0 STEP
1 1 -10 0 0 -1 0 0 0 1 0 0 0 1 child.ldr
0 FILE child.ldr
1 16 0 40 0 1 0 0 0 1 0 0 0 1 part.dat
0 STEP
1 16 20 40 0 1 0 0 0 1 0 0 0 1 part.dat
""")
    library = tmp_path / "library"
    (library / "parts").mkdir(parents=True)
    (library / "parts/part.dat").write_text(part(20))
    return path, library


def same_scene(left, right):
    assert left.step_count == right.step_count
    assert left.colors == right.colors
    assert left.meshes.keys() == right.meshes.keys()
    for name, mesh in left.meshes.items():
        other = right.meshes[name]
        assert mesh.title == other.title
        for field in ("triangles", "colors", "lines", "line_colors"):
            np.testing.assert_array_equal(getattr(mesh, field), getattr(other, field))
    for a, b in zip(left.instances, right.instances, strict=True):
        assert (a.identity, a.part, a.color, a.step, a.groups) == (
            b.identity,
            b.part,
            b.color,
            b.step,
            b.groups,
        )
        np.testing.assert_array_equal(a.transform, b.transform)
    np.testing.assert_array_equal(left.bounds(), right.bounds())


def test_scene_cache_survives_restart_and_lesson_copy(model, tmp_path, monkeypatch):
    path, library = model
    archive = tmp_path / "library.zip"
    with ZipFile(archive, "w") as output:
        output.write(library / "parts/part.dat", "parts/part.dat")
    first = load_scene(path, archive)
    copy = tmp_path / "student-copy"
    shutil.copytree(path.parent, copy)

    def no_parse(*args):
        pytest.fail("A cache hit must not parse the model again")

    monkeypatch.setattr(LDraw, "scene", no_parse)
    same_scene(first, load_scene(copy / path.name, archive))
    assert len(list((parts_cache() / "scenes").glob("*.npz"))) == 1
    code = """
import sys
from pathlib import Path
import little_tinker_rig.core.paths as paths
from little_tinker_rig.core.ldraw import LDraw
from little_tinker_rig.core.ldraw_cache import load_scene
paths.user_cache_path = lambda *a, **k: Path(sys.argv[3])
def no_parse(*args):
    raise AssertionError('A new process must reuse the scene cache')
LDraw.scene = no_parse
scene = load_scene(Path(sys.argv[1]), Path(sys.argv[2]))
assert scene.step_count == 3 and len(scene.instances) == 3
"""
    subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(copy / path.name),
            str(archive),
            str(parts_cache().parent),
        ],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def test_local_dependencies_and_new_overrides_invalidate_geometry(model):
    path, library = model
    first = load_scene(path, library)
    (library / "parts/part.dat").write_text(part(40))
    changed = load_scene(path, library)
    assert changed.meshes["part.dat"].bounds[1, 0] == 40
    override = path.parent / "part.dat"
    override.write_text(part(60))
    assert load_scene(path, library).meshes["part.dat"].bounds[1, 0] == 60
    override.unlink()
    same_scene(changed, load_scene(path, library))
    (library / "parts/part.dat").unlink()
    with pytest.raises(ValueError, match="Missing LDraw part"):
        load_scene(path, library)
    assert first.meshes["part.dat"].bounds[1, 0] == 20


def test_source_colors_and_format_changes_invalidate_cache(model, monkeypatch):
    path, library = model
    load_scene(path, library)
    before = path.stat()
    path.write_text(path.read_text().replace("10 0 0 1", "30 0 0 1", 1))
    # Content, not mtime or size, determines validity.
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert load_scene(path, library).instances[0].transform[0, 3] == 30
    (library / "LDConfig.ldr").write_text(
        "0 !COLOUR Red CODE 4 VALUE #FF0000 EDGE #222222\n"
    )
    assert load_scene(path, library).colors[4][0] == (1, 0, 0, 1)
    monkeypatch.setattr(ldraw_cache, "FORMAT", ldraw_cache.FORMAT + 1)
    with monkeypatch.context() as patch:

        def changed_parser(*args):
            raise ValueError("Changed parser")

        patch.setattr(LDraw, "scene", changed_parser)
        with pytest.raises(ValueError, match="Changed parser"):
            load_scene(path, library)


def test_changed_archive_and_corrupt_cache_are_rebuilt(model, tmp_path):
    path, _ = model
    archive = tmp_path / "parts.zip"
    for length in (20, 80):
        with ZipFile(archive, "w") as output:
            output.writestr("parts/part.dat", part(length))
        assert load_scene(path, archive).meshes["part.dat"].bounds[1, 0] == length
    files = list((parts_cache() / "scenes").glob("*.npz"))
    assert len(files) == 2
    for file in files:
        file.write_bytes(b"broken cache")
    assert load_scene(path, archive).meshes["part.dat"].bounds[1, 0] == 80


@pytest.mark.parametrize(
    "damage",
    [
        lambda data: data.update(colors=[]),
        lambda data: data["meshes"][0].__setitem__(1, 42),
    ],
)
def test_corrupt_cache_metadata_rebuilds_scene(model, damage, monkeypatch):
    path, library = model
    original = load_scene(path, library)
    cache = next((parts_cache() / "scenes").glob("*.npz"))
    with np.load(cache, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    metadata = json.loads(arrays["metadata"].tobytes())
    damage(metadata)
    arrays["metadata"] = np.frombuffer(json.dumps(metadata).encode(), dtype=np.uint8)
    np.savez(cache, **arrays)

    parsed = []
    parse = LDraw.scene

    def record(reader):
        parsed.append(True)
        return parse(reader)

    monkeypatch.setattr(LDraw, "scene", record)
    same_scene(original, load_scene(path, library))
    assert parsed == [True]


def test_failed_cache_write_preserves_model_and_cleans_temporary_file(
    model, monkeypatch
):
    path, library = model

    def full_disk(stream, **kwargs):
        stream.write(b"partial")
        raise OSError("Disk full")

    monkeypatch.setattr(ldraw_cache.np, "savez", full_disk)
    assert load_scene(path, library).step_count == 3
    assert not list((parts_cache() / "scenes").iterdir())


def test_cancelled_build_does_not_install_cache(model, monkeypatch):
    path, library = model
    parse = LDraw.scene
    cancelled = False

    def cancel_after_parse(reader):
        nonlocal cancelled
        scene = parse(reader)
        cancelled = True
        return scene

    monkeypatch.setattr(LDraw, "scene", cancel_after_parse)
    with pytest.raises(CancelledError):
        load_scene(path, library, cancelled=lambda: cancelled)
    assert not list((parts_cache() / "scenes").glob("*"))


def test_cancelled_build_stops_before_finishing_part_mesh(model, monkeypatch):
    from threading import Event

    path, library = model
    cancelled = Event()
    completed = []
    mesh = LDraw.mesh

    def cancel_during_mesh(reader, name):
        if name == "part.dat":
            cancelled.set()
        result = mesh(reader, name)
        completed.append(name)
        return result

    monkeypatch.setattr(LDraw, "mesh", cancel_during_mesh)
    with pytest.raises(CancelledError):
        load_scene(path, library, cancelled=cancelled.is_set)
    assert "part.dat" not in completed
    assert not list((parts_cache() / "scenes").glob("*"))
