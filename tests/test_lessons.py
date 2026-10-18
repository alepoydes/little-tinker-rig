import io
import json
from zipfile import ZipFile

import pytest

from little_tinker_rig.core.lessons import (
    Lesson,
    StudentProject,
    extract,
    pack,
    resource,
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
