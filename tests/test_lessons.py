import io
import json
from zipfile import ZipFile

import pytest

from pyblocks.core.lessons import Lesson, StudentProject, extract, pack, resource
from pyblocks.core.project import Project


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
    destination = tmp_path / "car.pyblocks"
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
    saved = tmp_path / "student.pyblocks"
    project.save(saved)
    project.progress["stage"] = "drive"
    recovered = StudentProject.restore(project.checkpoint())
    assert recovered.dirty
    saved.write_bytes(b"external edit")
    with pytest.raises(ValueError, match="changed outside"):
        recovered.save()
    assert saved.read_bytes() == b"external edit"
    recovered.save(tmp_path / "copy.pyblocks")
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
