import hashlib
import io
import json
import runpy
from concurrent.futures import CancelledError, ThreadPoolExecutor
from pathlib import Path
from threading import Event
from zipfile import ZipFile

import pytest

from little_tinker_rig.core import ldraw_parts
from little_tinker_rig.core.ldraw_parts import PartLibrary, resolve_library, subset
from little_tinker_rig.core.lessons import StudentProject, pack, robot_description


@pytest.fixture
def parts(tmp_path):
    files = {
        "LDConfig.ldr": "0 !COLOUR Lesson CODE 4 VALUE #AA0000 EDGE #222222\n",
        "parts/block.dat": "0 Authored test part\n1 16 0 0 0 1 0 0 0 1 0 0 0 1 triangle.dat\n",
        "p/triangle.dat": "0 Authored test triangle\n3 16 0 0 0 20 0 0 0 -20 0\n",
        "parts/unused.dat": "0 Not used\n3 16 0 0 0 10 0 0 0 10 0\n",
        "CAlicense.txt": "Test attribution\n",
        "CAlicense4.txt": "Additional test attribution\n",
        "CAreadme.txt": "Test library information\n",
    }
    archive = tmp_path / "complete.zip"
    with ZipFile(archive, "w") as z:
        for name, text in files.items():
            z.writestr("ldraw/" + name, text)
    spec = {
        "id": "test",
        "version": "1",
        "url": "https://example.invalid/complete.zip",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    }
    model = tmp_path / "model.ldr"
    model.write_text("0 Original model\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 block.dat\n")
    return archive, spec, model


def test_verified_cache_is_shared_without_extraction(parts, tmp_path, monkeypatch):
    archive, spec, _ = parts
    calls = []

    def fetch(*args, **kwargs):
        calls.append(args)
        response = io.BytesIO(archive.read_bytes())
        response.headers = {"Content-Length": str(archive.stat().st_size)}
        return response

    monkeypatch.setattr(ldraw_parts, "urlopen", fetch)
    progress = []
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(
                lambda _: resolve_library(
                    tmp_path,
                    spec,
                    download=True,
                    progress=lambda *p: progress.append(p),
                ),
                range(2),
            )
        )
    assert results[0] == results[1]
    assert len(calls) == 1
    assert progress[-1] == (archive.stat().st_size, archive.stat().st_size)
    assert list(results[0].parent.iterdir()) == [results[0]]
    with PartLibrary(results[0]) as library:
        assert library.read("PARTS/block.dat").startswith(b"0 Authored")
        assert set(library.used) == {"parts/block.dat"}


def test_mismatch_and_cancellation_leave_no_partial_library(parts, tmp_path):
    archive, spec, _ = parts
    cancelled = Event()
    with pytest.raises(CancelledError):
        resolve_library(
            tmp_path,
            spec,
            local=archive,
            progress=lambda *_: cancelled.set(),
            cancelled=cancelled.is_set,
        )
    assert not list(ldraw_parts.parts_cache().iterdir())
    installed = resolve_library(tmp_path, spec, local=archive)
    original = installed.read_bytes()
    bad = tmp_path / "wrong.zip"
    bad.write_bytes(b"not the expected archive")
    with pytest.raises(ValueError, match="does not match"):
        resolve_library(tmp_path, spec, local=bad)
    assert installed.read_bytes() == original
    assert list(installed.parent.iterdir()) == [installed]


@pytest.mark.parametrize("names", [["../escape.dat"], ["parts/a.dat", "PARTS/A.dat"]])
def test_archive_members_are_unambiguous_and_local(tmp_path, names):
    path = tmp_path / "bad.zip"
    with ZipFile(path, "w") as z:
        for name in names:
            z.writestr(name, "0 Example\n")
    with pytest.raises(ValueError):
        PartLibrary(path)


def test_subset_is_complete_and_preserves_attribution(parts):
    pytest.importorskip("numpy")
    from little_tinker_rig.core.ldraw import LDraw

    archive, spec, model = parts
    small = subset(model, archive, spec)
    with ZipFile(io.BytesIO(small)) as z:
        assert "parts/unused.dat" not in z.namelist()
        assert "p/triangle.dat" in z.namelist()
        assert z.read("calicense.txt") == b"Test attribution\n"
        assert z.read("calicense4.txt") == b"Additional test attribution\n"
        assert json.loads(z.read("source.json")) == spec
    path = model.parent / "subset.zip"
    path.write_bytes(small)
    with LDraw(model, path) as reader:
        scene = reader.scene()
    assert len(scene.instances) == 1
    assert scene.meshes["block.dat"].triangles.shape == (1, 3, 3)
    assert scene.colors[4][0][0] == pytest.approx(170 / 255)


def test_model_preparation_preserves_assembly_and_excludes_embedded_part_metadata(
    parts,
):
    np = pytest.importorskip("numpy")
    from little_tinker_rig.core.ldraw import LDraw

    prepare = runpy.run_path(
        str(Path(__file__).parents[1] / "tools/prepare_ldraw_model.py")
    )["prepare"]

    archive, _, model = parts
    license = "0 !LICENSE Redistributable under CCAL version 2.0 : see CAreadme.txt"
    source = f"""0 FILE main.ldr
0 Sample assembly
0 Author: Model author
{license}
1 4 10 20 30 1 0 0 0 1 0 0 0 1 123 - block.dat
0 STEP
1 1 0 0 0 1 0 0 0 1 0 0 0 1 child.ldr
0 FILE child.ldr
0 Subassembly
{license}
1 16 -10 0 0 -1 0 0 0 1 0 0 0 1 123 - block.dat
0 FILE 123 - block.dat
0 Embedded part
1 16 0 0 0 1 0 0 0 1 0 0 0 1 triangle.dat
0 !LICENSE Free for non-commercial use.
0 !LDCAD SNAP_CYL [gender=M]
"""
    with PartLibrary(archive) as library:
        prepared = prepare(source, library)
        with pytest.raises(ValueError, match="license"):
            prepare(
                source.replace(license, "0 !LICENSE All rights reserved", 1), library
            )
    assert "Free for non-commercial" not in prepared
    assert "0 FILE 123 - block.dat" not in prepared
    assert "0 Author: Model author" in prepared
    model.write_text(source)
    with LDraw(model, archive) as reader:
        original = reader.scene()
    model.write_text(prepared)
    with LDraw(model, archive) as reader:
        adapted = reader.scene()
    assert adapted.step_count == original.step_count == 2
    for old, new in zip(original.instances, adapted.instances, strict=True):
        assert (old.identity, old.color, old.step) == (
            new.identity,
            new.color,
            new.step,
        )
        np.testing.assert_array_equal(old.transform, new.transform)
    np.testing.assert_array_equal(original.bounds(), adapted.bounds())


def make_lesson(parts):
    archive, spec, model = parts
    root = model.parent / "lesson"
    root.mkdir()
    (root / "model.ldr").write_bytes(model.read_bytes())
    (root / "goal.md").write_text("Build a robot")
    (root / "robot.json").write_text(
        json.dumps({"format": 1, "model": "model.ldr", "library": spec})
    )
    (root / "lesson.json").write_text(
        json.dumps(
            {
                "format": 1,
                "id": "test",
                "title": "Test",
                "robot": "robot.json",
                "stages": [
                    {
                        "id": "build",
                        "title": "Build",
                        "mode": "assembly",
                        "description": "goal.md",
                    }
                ],
            }
        )
    )
    return root


def test_thin_save_and_offline_export_do_not_depend_on_cache(
    parts, tmp_path, monkeypatch
):
    pytest.importorskip("numpy")
    from little_tinker_rig.core.ldraw import LDraw
    from little_tinker_rig.core.project import Project

    archive, spec, _ = parts
    project = StudentProject.create(make_lesson(parts))
    program = Project(project.main, allow_draft=True)
    program.draft = "unfinished(\n"
    program.document.commit("", ("spare = 1\n",))
    program.save()
    thin = tmp_path / "student.ltr"
    project.save(thin)
    with ZipFile(thin) as z:
        assert not any(name.endswith((".dat", ".zip")) for name in z.namelist())
    cached = resolve_library(tmp_path, spec, local=archive)
    baseline = project.disk_hash
    project.progress["completed"] = ["build"]
    (project.lesson.root / "offline-parts.zip").write_bytes(b"User-owned resource")
    project.checkpoint()
    snapshot = pack(project.root)
    project.discard_working_copy()  # The export worker owns a snapshot, not GUI files.
    output = tmp_path / "offline.ltr"
    project.export(output, snapshot=snapshot)
    assert project.path == thin and project.disk_hash == baseline
    with ZipFile(output) as exported:
        assert "archive" not in json.loads(exported.read("project.json"))
    cached.unlink()
    monkeypatch.setattr(
        ldraw_parts,
        "urlopen",
        lambda *a, **k: pytest.fail("Offline project attempted network access"),
    )
    reopened = StudentProject.open(output)
    assert reopened.main.read_text() == "unfinished(\n"
    assert Project(reopened.main, allow_draft=True).document.state.scratch == (
        "spare = 1\n",
    )
    assert reopened.progress["completed"] == ["build"]
    robot = robot_description(reopened.lesson.root / "robot.json")
    assert robot["library"] == "offline-parts-1.zip"
    assert (
        reopened.lesson.root / "offline-parts.zip"
    ).read_bytes() == b"User-owned resource"
    library = resolve_library(reopened.lesson.root, robot["library"])
    with LDraw(reopened.lesson.root / robot["model"], library) as reader:
        assert len(reader.scene().instances) == 1


def test_lesson_waits_for_assembly_and_can_import_local_zip(
    parts, tmp_path, qt_app, monkeypatch
):
    import time

    from PySide6.QtWidgets import QFileDialog

    from little_tinker_rig.qt.app import Studio

    archive, _, _ = parts
    monkeypatch.setattr(
        ldraw_parts, "urlopen", lambda *a, **k: pytest.fail("Unexpected download")
    )
    window = Studio(tmp_path / "plain.py")
    try:
        window.lessons.open(make_lesson(parts))
        assembly = window.lessons.assembly
        assert not assembly.attempted and assembly.job is None
        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *a, **k: (str(archive), "")
        )
        assembly.open_library()
        deadline = time.monotonic() + 5
        while assembly.job and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert assembly.job is None
        assert assembly.scene is not None
        assert len(assembly.scene.instances) == 1
        assert not assembly.progress.isVisible()
    finally:
        window.recovery.close()
        window.deleteLater()


def test_gui_export_includes_unsaved_work_without_saving_original(
    parts, tmp_path, qt_app, monkeypatch
):
    import time

    from PySide6.QtWidgets import QFileDialog

    from little_tinker_rig.core.project import Project
    from little_tinker_rig.qt.app import Studio

    archive, spec, _ = parts
    resolve_library(tmp_path, spec, local=archive)
    output = tmp_path / "offline.ltr"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(output), "")
    )
    window = Studio(tmp_path / "plain.py")
    try:
        page = window.lessons.open(make_lesson(parts))
        project = page.lesson_project
        project.path = tmp_path / "original.ltr"
        window.lessons.save(project)
        baseline = project.path.read_bytes()
        page.session.document.commit("", ("spare = 42\n",))
        page.change_mode(1)
        page.code.setPlainText("unfinished(\n")
        window.lessons.export()
        deadline = time.monotonic() + 5
        while window.lessons.export_job and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert window.lessons.export_job is None
        assert output.is_file()
        assert window.lessons.export_action.isEnabled()
        assert project.path.read_bytes() == baseline
        assert project.dirty
        opened = StudentProject.open(output)
        assert opened.main.read_text() == "unfinished(\n"
        assert Project(opened.main, allow_draft=True).document.state.scratch == (
            "spare = 42\n",
        )
        with ZipFile(output) as z:
            assert "lesson/offline-parts.zip" in z.namelist()
    finally:
        window.recovery.close()
        window.deleteLater()
