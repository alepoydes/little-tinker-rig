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
        for stage in lesson.stages:
            assert set(stage["blocks"]) <= available
            for lang in ("en", "ru"):
                text = lesson.description(stage, lang)
                for name in re.findall(r"\]\(program:([^)]+)\)", text):
                    assert name in lesson.data["programs"], (path, name)
                assert "{%" not in text
        for name in lesson.data["programs"].values():
            assert lesson.file(name).is_file()
        # Licensing is explicit: only the MIT catalog enters these new packages.
        assert all("/website/" not in name for name in lesson.data["examples"].values())
