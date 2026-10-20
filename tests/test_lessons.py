import io
import json
import os
from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event
from zipfile import ZIP_STORED, ZipFile

import pytest

from little_tinker_rig.core.lessons import (
    Lesson,
    StudentProject,
    camera_values,
    extract,
    pack,
    resource,
    robot_description,
)
from little_tinker_rig.core.project import Project


@pytest.fixture
def lesson(tmp_path):
    root = tmp_path / "lesson"
    root.mkdir()
    (root / "goal.md").write_text("Drive to the finish.", encoding="utf-8")
    (root / "start.py").write_text("distance = 100\n", encoding="utf-8")
    (root / "lesson.json").write_text(
        json.dumps(
            {
                "format": 1,
                "id": "car",
                "title": {"en": "A car", "ru": "Машина"},
                "starter": "start.py",
                "stages": [
                    {
                        "id": "build",
                        "title": "Build",
                        "description": "goal.md",
                        "blocks": [],
                    },
                    {
                        "id": "drive",
                        "title": "Drive",
                        "description": "goal.md",
                        "blocks": ["wait"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


def test_extreme_assembly_camera_value_is_rejected_cleanly():
    with pytest.raises(ValueError, match="Invalid assembly camera"):
        camera_values({"center": [10**400, 0, 0], "extent": 10, "yaw": 0, "pitch": 0})


@pytest.mark.parametrize("coordinate", [True, 10**400])
def test_robot_description_rejects_non_numeric_port_coordinates(tmp_path, coordinate):
    (tmp_path / "robot.ldr").write_text("0 Robot\n", encoding="utf-8")
    path = tmp_path / "robot.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "model": "robot.ldr",
                "ports": {"A": [coordinate, 0, 0]},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Port markers need three finite coordinates"):
        robot_description(path)


def test_robot_description_rejects_boolean_format(tmp_path):
    (tmp_path / "robot.ldr").write_text("0 Robot\n", encoding="utf-8")
    path = tmp_path / "robot.json"
    path.write_text(
        json.dumps({"format": True, "model": "robot.ldr"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Unsupported robot description"):
        robot_description(path)


def test_lesson_rejects_boolean_format(lesson):
    path = lesson / "lesson.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["format"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported lesson format"):
        Lesson.load(lesson)


def test_connect_task_link_accepts_only_known_hub_transports(lesson):
    path = lesson / "lesson.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    link = {"kind": "connect", "label": "Choose hub", "target": "virtual"}
    data["stages"][0]["links"] = [link]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert Lesson.load(lesson).stages[0]["links"][0]["target"] == "virtual"

    link["target"] = "unknown"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown preferred hub transport"):
        Lesson.load(lesson)


def test_student_project_rejects_boolean_format(lesson):
    project = StudentProject.create(lesson)
    path = project.root / "project.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["format"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported student project format"):
        StudentProject(project.root)


def test_student_project_rejects_unrepresentable_assembly_step(lesson):
    project = StudentProject.create(lesson)
    path = project.root / "progress.json"
    progress = json.loads(path.read_text(encoding="utf-8"))
    progress["assembly"] = {"step": 2**31}
    path.write_text(json.dumps(progress), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid assembly state"):
        StudentProject(project.root)


@pytest.mark.parametrize(
    "extra",
    [
        {"folder": "start.py", "folder/helper.py": "start.py"},
        {"Robot/main.py": "start.py", "robot/helper.py": "start.py"},
    ],
)
def test_lesson_rejects_conflicting_student_program_paths(lesson, extra):
    manifest = lesson / "lesson.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["programs"] = {"main.py": "start.py", **extra}
    data["main"] = "main.py"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="conflict"):
        Lesson.load(lesson)


def test_pack_stops_between_files_when_cancelled(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b = 2\n", encoding="utf-8")
    cancelled = Event()
    original = ZipFile.write

    def write(archive, filename, arcname=None, compress_type=None, compresslevel=None):
        result = original(archive, filename, arcname, compress_type, compresslevel)
        cancelled.set()
        return result

    monkeypatch.setattr(ZipFile, "write", write)
    with pytest.raises(CancelledError):
        pack(tmp_path, cancelled=cancelled.is_set)


def test_pack_rejects_archive_larger_than_extract_limit_before_writing(
    tmp_path, monkeypatch
):
    large = tmp_path / "large.bin"
    with large.open("wb") as stream:
        stream.truncate(256 * 1024**2 + 1)

    def unexpected_write(*args, **kwargs):
        raise AssertionError("oversized archive was written")

    monkeypatch.setattr(ZipFile, "write", unexpected_write)
    with pytest.raises(ValueError, match="too large"):
        pack(tmp_path)


def test_pack_rejects_too_many_members_before_writing(tmp_path, monkeypatch):
    additions = {f"file-{index}.txt": "" for index in range(20001)}

    def unexpected_write(*args, **kwargs):
        raise AssertionError("oversized archive was written")

    monkeypatch.setattr(ZipFile, "writestr", unexpected_write)
    with pytest.raises(ValueError, match="too large"):
        pack(tmp_path, additions)


def test_independent_projects_and_portable_draft(lesson, tmp_path):
    first, second = StudentProject.create(lesson), StudentProject.create(lesson)
    assert first.root != second.root
    program = Project(first.main, allow_draft=True)
    program.draft = "if distance >\n"
    program.document.commit("", ("distance = 200\n",))
    program.save()
    first.progress.update(stage="drive", completed=["build"], hints={"drive": 1})
    destination = tmp_path / "car.ltr"
    first.save(destination)
    assert not first.dirty
    reopened = StudentProject.open(destination)
    draft = Project(reopened.main, allow_draft=True)
    assert draft.draft == "if distance >\n"
    assert draft.document.state.scratch == ("distance = 200\n",)
    assert reopened.stage["id"] == "drive"
    assert reopened.lesson.description(reopened.stage, "ru") == "Drive to the finish."
    assert second.main.read_text() == "distance = 100\n"
    reopened.progress["stage"] = "build"
    assert reopened.dirty
    assert reopened.main.read_text() == "if distance >\n"
    assert reopened.progress["completed"] == ["build"]


def test_task_points_links_and_scratch_seed_are_portable(lesson, tmp_path):
    (lesson / "idea.py").write_text("print('Try another distance')\n", encoding="utf-8")
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["scratch_seeds"] = {"main.py": ["idea.py"]}
    data["stages"][0]["points"] = 2
    data["stages"][0]["links"] = [
        {"kind": "markdown", "label": "More help", "target": "goal.md"},
        {"kind": "scratch", "label": "Idea", "target": "main.py"},
    ]
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    project = StudentProject.create(lesson)
    assert Project(project.main).document.state.scratch == (
        "print('Try another distance')\n",
    )
    project.progress["completed"] = ["build", "build"]
    assert project.score == (2, 3)
    project.checkpoint()
    assert project.progress["completed"] == ["build", "build"]
    destination = tmp_path / "project.ltr"
    project.save(destination)
    archived = StudentProject.open(destination)
    assert archived.data["id"] == project.data["id"]
    assert archived.data["origin"] == str(lesson.resolve())
    assert archived.score == (2, 3)
    assert StudentProject.latest(lesson).root == project.root
    archived.discard_working_copy()


@pytest.mark.parametrize("points", [-1, True, "3"])
def test_task_points_reject_invalid_values(lesson, points):
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][0]["points"] = points
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="points"):
        Lesson.load(lesson)


def test_device_check_requires_distinct_devices_on_distinct_ports(lesson):
    (lesson / "robot.ldr").write_text("0 Robot\n", encoding="utf-8")
    robot_path = lesson / "robot.json"
    robot = {
        "format": 1,
        "model": "robot.ldr",
        "devices": [
            {"instance": "left", "name": "Left", "port": "A", "type": "motor"},
            {"instance": "right", "name": "Right", "port": "B", "type": "motor"},
        ],
    }
    robot_path.write_text(json.dumps(robot), encoding="utf-8")
    lesson_path = lesson / "lesson.json"
    data = json.loads(lesson_path.read_text(encoding="utf-8"))
    data["robot"] = "robot.json"
    stage = data["stages"][0]
    stage.update(check="devices", devices=["left", "right"])
    lesson_path.write_text(json.dumps(data), encoding="utf-8")
    Lesson.load(lesson)

    for required in ([], ["left", "left"]):
        stage["devices"] = required
        lesson_path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="distinct required devices"):
            Lesson.load(lesson)
    del stage["devices"]
    lesson_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct required devices"):
        Lesson.load(lesson)

    robot["devices"][1]["port"] = "A"
    robot_path.write_text(json.dumps(robot), encoding="utf-8")
    with pytest.raises(ValueError, match="unique ports"):
        robot_description(robot_path)


def test_localized_task_card_markdown_is_packaged_and_validated(lesson):
    (lesson / "panel-en.md").write_text("Build a car.\n", encoding="utf-8")
    (lesson / "panel-ru.md").write_text("Собери машину.\n", encoding="utf-8")
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][0]["panel"] = {"en": "panel-en.md", "ru": "panel-ru.md"}
    data["stages"][0]["panel_actions"] = False
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = Lesson.load(lesson)
    assert loaded.panel_text(loaded.stages[0], "ru") == "Собери машину.\n"
    assert loaded.panel_text(loaded.stages[1], "en") == "Drive"
    assert b"panel-ru.md" in loaded.archive()
    data["stages"][0]["panel_actions"] = "no"
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="panel_actions"):
        Lesson.load(lesson)


def test_one_instruction_file_uses_stable_task_sections(lesson):
    (lesson / "full.md").write_text(
        '# A car\n\n<a name="build"></a>\n\n## Build\n\nAssemble it.\n\n'
        '<a name="drive"></a>\n\n## Drive\n\nMake it move.\n',
        encoding="utf-8",
    )
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["instructions"] = "full.md"
    for stage in data["stages"]:
        stage["description"] = f"full.md#{stage['id']}"
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = Lesson.load(lesson)
    assert "Assemble it." in loaded.description(loaded.stages[0])
    assert "Make it move." not in loaded.description(loaded.stages[0])
    assert "Make it move." in loaded.description(loaded.stages[1])
    assert b"full.md" in loaded.archive()
    data["stages"][1]["description"] = "goal.md"
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="sections of lesson instructions"):
        Lesson.load(lesson)


def test_legacy_stage_files_form_one_navigable_instruction_document(lesson):
    (lesson / "finish.md").write_text(
        "# Finish\n\nStop at the line.\n", encoding="utf-8"
    )
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][1]["description"] = "finish.md"
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = Lesson.load(lesson)
    document, source = loaded.instructions_document()
    assert source == "goal.md"
    assert "Drive to the finish." in document
    assert "Stop at the line." in document
    assert '<a name="task-build"></a>' in document
    assert '<a name="task-drive"></a>' in document
    assert loaded.instructions_anchor(loaded.stages[1]) == "task-drive"


def test_package_and_recovery_keep_original_save_baseline(lesson, tmp_path):
    archive = tmp_path / "car.pylesson"
    archive.write_bytes(pack(lesson))
    project = StudentProject.create(archive)
    saved = tmp_path / "student.ltr"
    project.save(saved)
    project.progress["stage"] = "drive"
    recovered = StudentProject.restore(project.checkpoint())
    assert recovered.dirty
    saved.write_bytes(b"external edit")
    with pytest.raises(ValueError, match="changed outside"):
        recovered.save()
    assert saved.read_bytes() == b"external edit"
    recovered.save(tmp_path / "copy.ltr")
    assert not recovered.dirty


def test_saved_template_attempt_retains_archive_and_dirty_baseline(lesson, tmp_path):
    project = StudentProject.create(lesson)
    created = project.data["created"]
    saved = tmp_path / "student.ltr"
    project.save(saved)
    project.progress["completed"].append("build")
    project.pending = True
    project.checkpoint()

    resumed = StudentProject.latest(lesson)
    assert resumed.path == saved
    assert resumed.disk_hash == project.disk_hash
    assert resumed.data["created"] == created
    assert resumed.dirty
    assert resumed.score == (1, 2)

    saved.write_bytes(b"external edit")
    with pytest.raises(ValueError, match="changed outside"):
        resumed.save()
    assert saved.read_bytes() == b"external edit"

    copy = tmp_path / "copy.ltr"
    resumed.save(copy)
    reopened = StudentProject.latest(lesson)
    assert reopened.path == copy
    assert not reopened.dirty
    with ZipFile(copy) as archive:
        assert "archive" not in json.loads(archive.read("project.json"))
    assert "archive" not in StudentProject.open(copy).data


@pytest.mark.parametrize("save_as", [False, True])
def test_stale_recovery_uses_newer_saved_attempt_baseline(lesson, tmp_path, save_as):
    project = StudentProject.create(lesson)
    destination = tmp_path / "student.ltr"
    project.save(destination)
    stale_recovery = project.checkpoint()

    project.progress["completed"].append("build")
    if save_as:
        destination = tmp_path / "copy.ltr"
    project.save(destination)
    restored = StudentProject.restore(stale_recovery)

    assert restored.path == destination
    assert restored.disk_hash == project.disk_hash
    assert restored.saved_progress == project.saved_progress
    assert not restored.dirty
    restored.save()


def test_unsaved_attempt_restores_pending_recovery_state(lesson):
    project = StudentProject.create(lesson)
    project.pending = True
    restored = StudentProject.restore(project.checkpoint())
    assert restored.path is None
    assert restored.pending
    assert restored.dirty


def test_save_as_and_export_require_explicit_overwrite(lesson, tmp_path):
    first = StudentProject.create(lesson)
    second = StudentProject.create(lesson)
    destination = tmp_path / "existing.ltr"
    first.save(destination)
    original = destination.read_bytes()

    with pytest.raises(FileExistsError):
        second.save(destination)
    assert destination.read_bytes() == original
    assert second.path is None

    with pytest.raises(FileExistsError):
        second.export(destination)
    assert destination.read_bytes() == original

    second.save(destination, overwrite=True)
    assert StudentProject.open(destination).data["id"] == second.data["id"]

    exported = tmp_path / "offline.ltr"
    exported.write_bytes(b"Previous export")
    second.export(exported, overwrite=True)
    assert StudentProject.open(exported).data["id"] == second.data["id"]


@pytest.mark.parametrize(
    "name", ["../escaped", "/absolute", "a/../../escaped", "C:/file", "a\\b"]
)
def test_archive_paths_are_checked_before_extraction(tmp_path, name):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("good.txt", "safe")
        archive.writestr(name, "unsafe")
    with pytest.raises(ValueError):
        extract(data.getvalue(), tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_archive_file_directory_conflicts_fail_before_writing(tmp_path):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("good.txt", "safe")
        archive.writestr("folder", "file")
        archive.writestr("folder/child.txt", "unreachable")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="conflict"):
        extract(data.getvalue(), destination)
    assert not destination.exists()


def test_archive_rejects_existing_file_parent_without_partial_extraction(tmp_path):
    destination = tmp_path / "output"
    destination.mkdir()
    blocker = destination / "folder"
    blocker.write_text("keep", encoding="utf-8")
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("good.txt", "safe")
        archive.writestr("folder/child.txt", "unreachable")
    with pytest.raises(ValueError, match="conflict"):
        extract(data.getvalue(), destination)
    assert blocker.read_text(encoding="utf-8") == "keep"
    assert not (destination / "good.txt").exists()


def test_corrupt_archive_member_cannot_overwrite_existing_files(tmp_path):
    destination = tmp_path / "output"
    destination.mkdir()
    existing = destination / "notes.txt"
    existing.write_text("Original notes", encoding="utf-8")
    data = io.BytesIO()
    with ZipFile(data, "w", ZIP_STORED) as archive:
        archive.writestr("notes.txt", "Replacement notes")
        archive.writestr("last.txt", "Unique payload for CRC corruption")
    corrupted = bytearray(data.getvalue())
    offset = corrupted.index(b"Unique payload for CRC corruption")
    corrupted[offset] ^= 1

    with pytest.raises(ValueError, match="valid LittleTinker Rig archive"):
        extract(bytes(corrupted), destination)
    assert existing.read_text(encoding="utf-8") == "Original notes"
    assert not (destination / "last.txt").exists()


def test_extract_replace_failure_keeps_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "output"
    destination.mkdir()
    existing = destination / "notes.txt"
    existing.write_text("Original notes", encoding="utf-8")
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("notes.txt", "Replacement notes")

    original_replace = Path.replace

    def fail_replace(source, target):
        if target == existing:
            raise OSError("simulated replacement failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replacement failure"):
        extract(data.getvalue(), destination)
    assert existing.read_text(encoding="utf-8") == "Original notes"
    assert {path.name for path in destination.iterdir()} == {"notes.txt"}


def test_archive_rejects_case_collisions_in_parent_directories(tmp_path):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("good.txt", "safe")
        archive.writestr("Robot/left.py", "left")
        archive.writestr("robot/right.py", "right")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="conflict"):
        extract(data.getvalue(), destination)
    assert not destination.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot create both directories")
def test_pack_rejects_case_collisions_in_parent_directories(tmp_path):
    project = tmp_path / "project"
    (project / "Robot").mkdir(parents=True)
    (project / "robot").mkdir()
    (project / "Robot" / "left.py").write_text("left = 1\n")
    (project / "robot" / "right.py").write_text("right = 1\n")
    with pytest.raises(ValueError, match="conflict"):
        pack(project)


@pytest.mark.parametrize(
    "name",
    ["CON.txt", "aux/child.py", "folder./main.py", "bad?.py", " leading.py", "end "],
)
def test_extract_rejects_names_that_windows_cannot_preserve(tmp_path, name):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("good.txt", "safe")
        archive.writestr(name, "bad")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="not portable"):
        extract(data.getvalue(), destination)
    assert not destination.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows cannot create these filenames")
@pytest.mark.parametrize(
    "name",
    ["CON.txt", "aux/child.py", "folder./main.py", "bad?.py", " leading.py", "end "],
)
def test_pack_rejects_names_that_windows_cannot_preserve(tmp_path, name):
    project = tmp_path / "project"
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("bad", encoding="utf-8")
    with pytest.raises(ValueError, match="not portable"):
        pack(project)


def test_pack_checks_case_collisions_with_generated_archive_files(tmp_path):
    (tmp_path / "lesson.json").write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="conflict"):
        pack(tmp_path, {"LESSON.JSON": "replacement"})


def test_pack_only_ignores_cache_directories_inside_project(tmp_path):
    project = tmp_path / "__pycache__" / "project"
    project.mkdir(parents=True)
    (project / "main.py").write_text("print(42)\n", encoding="utf-8")
    cache = project / "__pycache__"
    cache.mkdir()
    (cache / "main.pyc").write_bytes(b"cache")
    with ZipFile(io.BytesIO(pack(project))) as archive:
        assert archive.namelist() == ["main.py"]


def test_lesson_references_cannot_escape(lesson):
    data = json.loads((lesson / "lesson.json").read_text())
    data["stages"][0]["description"] = "../outside.md"
    (lesson / "lesson.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escapes"):
        Lesson.load(lesson)


@pytest.mark.parametrize(
    "link",
    [
        {"kind": "markdown", "label": "Outside", "target": "../outside.md"},
        {"kind": "program", "label": "Unknown", "target": "missing.py"},
        {"kind": "shell", "label": "Run"},
    ],
)
def test_task_links_reject_unsafe_or_unknown_targets(lesson, link):
    data = json.loads((lesson / "lesson.json").read_text(encoding="utf-8"))
    data["stages"][0]["links"] = [link]
    (lesson / "lesson.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        Lesson.load(lesson)


def test_symlink_resources_are_not_followed(lesson, tmp_path):
    (lesson / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        resource(lesson, "escape/secret")
    with pytest.raises(ValueError, match="symbolic"):
        pack(lesson)


def test_markdown_stage_sections_ignore_code_and_keep_subsections():
    from little_tinker_rig.documentation import section

    text = """# Lesson
<a name="drive"></a>
## Drive
A goal.
```python
# Not a section
## Not a boundary
```
### Hints
Try again.
## Finish
Save.
"""
    selected = section(text, "drive")
    assert selected.startswith("## Drive\n")
    assert "### Hints\nTry again." in selected
    assert "Not a boundary" in selected
    assert "Save." not in selected
    with pytest.raises(ValueError, match="Missing Markdown section"):
        section(text, "missing")


@pytest.mark.parametrize(
    ("opening", "embedded", "closing"),
    [
        ("```python", "~~~", "```"),
        ("````python", "```", "````"),
        ("~~~python", "```", "~~~"),
        ("```python", "``` still code", "```"),
    ],
)
def test_markdown_fences_require_matching_marker_and_length(opening, embedded, closing):
    from little_tinker_rig.documentation import heading_anchors, section

    text = f"""# Lesson
## Drive
Before code.
{opening}
{embedded}
<a name="hidden"></a>
## Fake section
{closing}
### Hint
After code.
## Finish
Done.
"""
    assert list(heading_anchors(text)) == [
        ["lesson"],
        ["drive"],
        ["hint"],
        ["finish"],
    ]
    selected = section(text, "drive")
    assert "## Fake section\n" in selected
    assert "### Hint\nAfter code." in selected
    assert "## Finish\n" not in selected
    with pytest.raises(ValueError, match="Missing Markdown section"):
        section(text, "hidden")


@pytest.mark.parametrize("line", ["    ```", "```invalid`info"])
def test_invalid_code_fence_does_not_hide_following_heading(line):
    from little_tinker_rig.documentation import heading_anchors, section

    text = f"# Lesson\n{line}\n## Real section\nContent.\n"
    assert list(heading_anchors(text)) == [["lesson"], ["real-section"]]
    assert section(text, "real-section") == "## Real section\nContent.\n"


def test_multifile_lesson_snapshot_is_independent_of_installed_examples(
    lesson, tmp_path, monkeypatch
):
    import little_tinker_rig.core.lessons as lessons
    from little_tinker_rig.pybricks.program import Program

    installed = tmp_path / "examples"
    installed.mkdir()
    (installed / "main.py").write_text("from shared import answer\nprint(answer)\n")
    (installed / "shared.py").write_text("answer = 42\n")
    (installed / "LICENSE.txt").write_text("License and attribution\n")
    monkeypatch.setattr(lessons, "examples_directory", lambda: installed)
    (lesson / "blocks").mkdir()
    (lesson / "blocks" / "collection.toml").write_text('id = "lesson"\nversion = "1"\n')
    data = json.loads((lesson / "lesson.json").read_text())
    data.update(
        collection="blocks",
        examples={f"code/{n}": n for n in ("main.py", "shared.py", "LICENSE.txt")},
        programs={
            f"robot/{n}": f"code/{n}" for n in ("main.py", "shared.py", "LICENSE.txt")
        },
        main="robot/main.py",
    )
    data["stages"][0]["program"] = "robot/main.py"
    (lesson / "lesson.json").write_text(json.dumps(data))
    portable = tmp_path / "portable.pylesson"
    portable.write_bytes(Lesson.load(lesson).archive())
    # A .pylesson must work on another installation with no original examples.
    monkeypatch.setattr(lessons, "examples_directory", lambda: tmp_path / "absent")
    project = StudentProject.create(portable)
    assert "examples" not in project.lesson.data
    assert project.main.name == "main.py"
    for name in ("main.py", "shared.py"):
        settings = json.loads((project.main.parent / (name + ".ltr.json")).read_text())
        assert (
            project.main.parent / settings["collections"][0]
        ).resolve() == project.lesson.root / "blocks"
    assert (
        project.main.parent / "LICENSE.txt"
    ).read_text() == "License and attribution\n"
    snapshot = Program(project.main)
    try:
        assert {p.name for p in snapshot.sources} == {"main.py", "shared.py"}
    finally:
        snapshot.cleanup()
    project.main.write_text("# Student revision\n")
    saved = tmp_path / "student.ltr"
    project.save(saved)
    reopened = StudentProject.open(saved)
    assert reopened.main.read_text() == "# Student revision\n"
    assert reopened.lesson.file("code/main.py").read_text().startswith("from shared")
    assert (installed / "main.py").read_text().startswith("from shared")


@pytest.mark.parametrize(
    "change",
    [
        {"main": "missing.py"},
        {"programs": {"../main.py": "start.py"}, "main": "../main.py"},
        {
            "programs": {"main.py": "start.py", "./main.py": "start.py"},
            "main": "main.py",
        },
        {"programs": {"LICENSE.txt": "goal.md"}, "main": "LICENSE.txt"},
        {"examples": {"goal.md": "first_drive.py"}},
    ],
)
def test_lesson_program_manifest_rejects_ambiguous_or_unsafe_paths(lesson, change):
    data = json.loads((lesson / "lesson.json").read_text()) | change
    (lesson / "lesson.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Lesson.load(lesson)


def test_bundled_pybricks_lessons_have_resolvable_materials_programs_and_palettes():
    import re

    from little_tinker_rig.core.lessons import lessons_directory
    from little_tinker_rig.core.snippets import builtin_snippets

    available = {s.identity for s in builtin_snippets()}
    paths = sorted((lessons_directory() / "pybricks").glob("*/lesson.json"))
    assert paths
    for path in paths:
        lesson = Lesson.load(path.parent)
        assert lesson.data["kind"] == "project"
        for stage in lesson.stages:
            assert set(stage["blocks"]) <= available
            for lang in ("en", "ru"):
                text = lesson.description(stage, lang)
                goal = stage["goal"][lang]
                assert goal and "one controlled change" not in goal
                if stage["id"].startswith("run-"):
                    assert stage["program"] in goal
                for name in re.findall(r"\]\(program:([^)]+)\)", text):
                    assert name in lesson.data["programs"], (path, name)
                assert "{%" not in text
        for name in lesson.data["programs"].values():
            assert lesson.file(name).is_file()
        # Licensing is explicit: only the MIT catalog enters these new packages.
        assert all("/website/" not in name for name in lesson.data["examples"].values())
