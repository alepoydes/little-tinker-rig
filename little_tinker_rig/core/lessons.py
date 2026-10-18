"""Portable lesson materials and independent student workspaces.

The working directory contains ordinary files. Archives are atomic snapshots;
opening or navigating a lesson never rewrites a student's program.
"""

import hashlib
import io
import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time_ns
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from little_tinker_rig.documentation import section
from little_tinker_rig.examples import examples_directory

from .paths import personal_collection, resource
from .project import atomic_write

WORKSPACES = ("program", "control", "help", "block_editor", "assembly")


def localized(value, language="en") -> str:
    if isinstance(value, str):
        return value
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("en"), str)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    ):
        raise ValueError("Localized text needs an English value")
    result = value.get(language, value["en"])
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def camera_values(state):
    try:
        values = (*state["center"], state["extent"], state["yaw"], state["pitch"])
        valid = len(values) == 6 and all(
            type(v) in (int, float) and math.isfinite(v) for v in values
        )
        if valid and values[3] > 0 and abs(values[5]) < 90:
            return values
    except (KeyError, TypeError):
        pass
    raise ValueError("Invalid assembly camera")


def robot_description(path):
    data = read_json(path)
    if not isinstance(data, dict) or data.get("format") != 1:
        raise ValueError("Unsupported robot description")
    if not resource(path.parent, data.get("model", "")).is_file():
        raise ValueError("Missing robot model")
    from .ldraw_parts import validate_reference

    library = data.get("library", ".")
    if isinstance(library, dict):
        validate_reference(library)
    elif not resource(path.parent, library).exists():
        raise ValueError("Missing robot parts library")
    localized(data.get("title", ""))
    localized(data.get("description", ""))
    for key in ("parts", "steps", "ports"):
        if not isinstance(data.get(key, {}), dict):
            raise ValueError(f"Robot {key} must be a mapping")
    for text in data.get("parts", {}).values():
        localized(text)
    for number, step in data.get("steps", {}).items():
        if not number.isdecimal() or int(number) < 1 or not isinstance(step, dict):
            raise ValueError("Invalid robot step")
        localized(step.get("text", ""))
        if "camera" in step:
            camera_values(step["camera"])
    for point in data.get("ports", {}).values():
        if (
            not isinstance(point, list)
            or len(point) != 3
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point)
        ):
            raise ValueError("Port markers need three finite coordinates")
    devices = data.get("devices", [])
    if not isinstance(devices, list):
        raise ValueError("Robot devices must be a list")
    identities = set()
    for device in devices:
        if (
            not isinstance(device, dict)
            or not isinstance(device.get("instance"), str)
            or device["instance"] in identities
        ):
            raise ValueError("Robot devices need unique instance ids")
        identities.add(device["instance"])
        localized(device.get("name"))
        if device.get("port") not in tuple("ABCDEF") or not isinstance(
            device.get("type"), str
        ):
            raise ValueError("Invalid robot device connection")
    return data


def extract(data: bytes, destination: Path):
    """Validate the entire member list before creating any files."""
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if (
                len(members) > 20000
                or sum(m.file_size for m in members) > 256 * 1024**2
            ):
                raise ValueError("The project archive is too large")
            paths = [resource(destination, m.filename) for m in members]
            if len(set(paths)) != len(paths):
                raise ValueError("Duplicate archive entries")
            for member, path in zip(members, paths, strict=True):
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(member))
    except BadZipFile as error:
        raise ValueError("Not a valid LittleTinker Rig archive") from error


def pack(directory: Path, additions=None) -> bytes:
    additions = additions or {}
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("Packages cannot contain symbolic links")
            name = path.relative_to(directory).as_posix()
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and name not in additions
            ):
                archive.write(path, name)
        for name, data in additions.items():
            resource(directory, name)
            archive.writestr(name, data)
    return output.getvalue()


@dataclass(frozen=True)
class Lesson:
    root: Path
    data: dict

    @classmethod
    def load(cls, root: Path):
        root = root.resolve()
        data = read_json(root / "lesson.json")
        if not isinstance(data, dict) or data.get("format") != 1:
            raise ValueError("Unsupported lesson format")
        if not isinstance(data.get("id"), str) or not data["id"]:
            raise ValueError("A lesson needs an id")
        localized(data.get("title"))
        localized(data.get("group", ""))
        if data.get("kind", "lesson") not in ("lesson", "project"):
            raise ValueError("Unknown learning activity kind")
        lesson = cls(root, data)
        if "instructions" in data:
            instructions = data["instructions"]
            localized(instructions)
            for name in (
                instructions.values()
                if isinstance(instructions, dict)
                else (instructions,)
            ):
                if "#" in name:
                    raise ValueError(
                        "Lesson instructions must name a whole Markdown file"
                    )
                lesson.material(name)
        if "panel_intro" in data:
            intro = data["panel_intro"]
            localized(intro)
            for name in intro.values() if isinstance(intro, dict) else (intro,):
                lesson.material(name)
        examples = data.get("examples", {})
        if not isinstance(examples, dict):
            raise ValueError("Lesson examples must map local paths to bundled files")
        targets = set()
        for name, origin in examples.items():
            target = resource(root, name)
            if target in targets or target.exists():
                raise ValueError(f"A bundled example shadows a lesson file: {name}")
            targets.add(target)
            if not resource(examples_directory(), origin).is_file():
                raise ValueError(f"Missing bundled example: {origin}")
        programs = data.get("programs", {})
        if not isinstance(programs, dict):
            raise ValueError("Lesson programs must map workspace paths to lesson files")
        targets = set()
        for name, origin in programs.items():
            target = resource(root / "programs", name)
            if target in targets:
                raise ValueError(f"Duplicate lesson program: {name}")
            targets.add(target)
            if not lesson.file(origin).is_file():
                raise ValueError(f"Invalid lesson program: {name}")
        if (programs or "main" in data) and (
            not isinstance(data.get("main"), str) or data["main"] not in programs
        ):
            raise ValueError("Lesson main must name an included program")
        if programs and not data["main"].endswith(".py"):
            raise ValueError("Lesson main must be a Python program")
        stages = data.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError("A lesson needs at least one stage")
        ids = set()
        for stage in stages:
            if not isinstance(stage, dict) or not isinstance(stage.get("id"), str):
                raise ValueError("A stage needs an id")
            if not stage["id"] or stage["id"] in ids:
                raise ValueError("Stage ids must be unique and nonempty")
            ids.add(stage["id"])
            localized(stage.get("title"))
            localized(stage.get("goal", stage["title"]))
            if type(stage.get("points", 1)) is not int or stage.get("points", 1) < 0:
                raise ValueError("Task points must be a nonnegative integer")
            description = stage.get("description")
            localized(description)
            for name in (
                description.values() if isinstance(description, dict) else [description]
            ):
                lesson.material(name)
            if "panel" in stage:
                panel = stage["panel"]
                localized(panel)
                for name in panel.values() if isinstance(panel, dict) else (panel,):
                    lesson.material(name)
            if type(stage.get("panel_actions", True)) is not bool:
                raise ValueError("Task panel_actions must be a boolean")
            blocks = stage.get("blocks", [])
            if not isinstance(blocks, list) or not all(
                isinstance(b, str) for b in blocks
            ):
                raise ValueError("Stage blocks must be a list of snippet ids")
            if stage.get("mode", "program") not in ("assembly", "program", "control"):
                raise ValueError("Unknown lesson stage mode")
            if stage.get("check", "manual") not in ("manual", "devices"):
                raise ValueError("Unknown completion check")
            hints = stage.get("hints", [])
            if not isinstance(hints, list):
                raise ValueError("Hints must be a list")
            for hint in hints:
                localized(hint)
            for key in ("operations", "devices"):
                if not isinstance(stage.get(key, []), list) or not all(
                    isinstance(v, str) for v in stage.get(key, [])
                ):
                    raise ValueError(f"Stage {key} must be a list of names")
            if "starter" in stage and not lesson.file(stage["starter"]).is_file():
                raise ValueError("Missing starter program")
            if "program" in stage and (
                not isinstance(stage["program"], str)
                or stage["program"] not in programs
                or not stage["program"].endswith(".py")
            ):
                raise ValueError("A stage must name an included Python program")
            links = stage.get("links", [])
            if not isinstance(links, list):
                raise ValueError("Task links must be a list")
            for link in links:
                if not isinstance(link, dict) or link.get("kind") not in (
                    "markdown",
                    "program",
                    "assembly",
                    "control",
                    "connect",
                    "devices",
                    "scratch",
                ):
                    raise ValueError("Unknown task link")
                localized(link.get("label"))
                kind = link["kind"]
                target = link.get("target")
                if kind == "markdown":
                    localized(target)
                    names = target.values() if isinstance(target, dict) else (target,)
                    for name in names:
                        lesson.material(name)
                elif kind in ("program", "scratch"):
                    if (
                        not isinstance(target, str)
                        or target
                        not in (
                            *programs,
                            data.get("main", "main.py"),
                        )
                        or not target.endswith(".py")
                    ):
                        raise ValueError("Task link must name a student Python file")
                elif target is not None:
                    raise ValueError("Workspace task links have no target")
            steps = stage.get("assembly")
            if steps is not None and (
                not isinstance(steps, list)
                or len(steps) != 2
                or not all(type(n) is int and n >= 1 for n in steps)
                or steps[0] > steps[1]
            ):
                raise ValueError(
                    "Assembly ranges use inclusive, one-based step numbers"
                )
        if "instructions" in data:
            for stage in stages:
                languages = {"en"}
                for value in (data["instructions"], stage["description"]):
                    if isinstance(value, dict):
                        languages.update(value)
                for code in languages:
                    document = localized(data["instructions"], code)
                    section_name = localized(stage["description"], code)
                    path, _, anchor = section_name.partition("#")
                    if path != document or (len(stages) > 1 and not anchor):
                        raise ValueError(
                            "Stage descriptions must reference sections of lesson instructions"
                        )
        for key in ("robot", "starter", "collection"):
            if key in data and not lesson.file(data[key]).exists():
                raise ValueError(f"Missing lesson {key}: {data[key]}")
        seeds = data.get("scratch_seeds", {})
        if not isinstance(seeds, dict):
            raise ValueError("Scratch seeds must map student programs to lesson files")
        for name, fragments in seeds.items():
            if (
                not isinstance(name, str)
                or name
                not in (
                    *programs,
                    data.get("main", "main.py"),
                )
                or not name.endswith(".py")
            ):
                raise ValueError("Scratch seed must name a student Python program")
            if not isinstance(fragments, list) or not all(
                isinstance(fragment, str) and lesson.file(fragment).is_file()
                for fragment in fragments
            ):
                raise ValueError("Scratch seeds must name included files")
        if "robot" in data:
            robot = robot_description(resource(root, data["robot"]))
            devices = {d["instance"] for d in robot.get("devices", [])}
            if any(set(s.get("devices", [])) - devices for s in stages):
                raise ValueError("A stage names an unknown robot device")
        elif any(
            s.get("mode") == "assembly"
            or s.get("check") == "devices"
            or any(link["kind"] == "assembly" for link in s.get("links", []))
            for s in stages
        ):
            raise ValueError("Assembly and device checks need a robot description")
        return lesson

    def file(self, name):
        target = resource(self.root, name)
        origin = self.data.get("examples", {}).get(name)
        return resource(examples_directory(), origin) if origin else target

    def material(self, name):
        path, _, anchor = name.partition("#")
        text = self.file(path).read_text(encoding="utf-8")
        return section(text, anchor) if anchor else text

    def archive(self):
        # Resolve installed examples once. Portable archives never depend on the
        # installed catalog, so updates cannot alter an existing student's lesson.
        data = dict(self.data)
        references = data.pop("examples", {})
        additions = {name: self.file(name).read_bytes() for name in references}
        additions["lesson.json"] = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        return pack(self.root, additions)

    @property
    def stages(self):
        return self.data["stages"]

    def description(self, stage, language="en"):
        return self.material(localized(stage["description"], language))

    def instructions_document(self, language="en"):
        """Return one readable document and its relative-link base for this lesson."""
        if "instructions" in self.data:
            name = localized(self.data["instructions"], language)
            return self.material(name), name
        names = [localized(stage["description"], language) for stage in self.stages]
        sources = [name.partition("#")[0] for name in names]
        if len(set(sources)) == 1 and (
            len(self.stages) == 1 or all("#" in name for name in names)
        ):
            return self.material(sources[0]), sources[0]
        parts = [f"# {localized(self.data['title'], language)}"]
        for stage, name in zip(self.stages, names, strict=True):
            title = localized(stage["title"], language)
            body = self.material(name).strip()
            if body.startswith("#"):
                heading, _, rest = body.partition("\n")
                heading = heading.lstrip("# ").strip()
                body = (
                    rest.strip()
                    if heading.casefold() == title.casefold()
                    else f"### {heading}\n\n{rest.strip()}"
                )
            parts.append(f'<a name="task-{stage["id"]}"></a>\n\n## {title}\n\n{body}')
        return "\n\n".join(parts) + "\n", sources[0]

    def instructions_anchor(self, stage, language="en"):
        name = localized(stage["description"], language)
        source, _, anchor = name.partition("#")
        if "instructions" in self.data:
            return anchor
        sources = {
            localized(item["description"], language).partition("#")[0]
            for item in self.stages
        }
        if len(self.stages) == 1 or (
            sources == {source}
            and all(
                "#" in localized(item["description"], language) for item in self.stages
            )
        ):
            return anchor
        return f"task-{stage['id']}"

    def panel_text(self, stage, language="en"):
        if "panel" in stage:
            return self.material(localized(stage["panel"], language))
        return localized(stage.get("goal", stage["title"]), language)


class StudentProject:
    """One archive and its private, recoverable working directory."""

    def __init__(
        self, root: Path, path: Path | None = None, disk_hash=None, *, retain=False
    ):
        self.root = root.resolve()
        self.path = path.resolve() if path else None
        self.disk_hash = disk_hash
        self.retain = retain
        self.data = read_json(self.root / "project.json")
        if not isinstance(self.data, dict) or self.data.get("format") != 1:
            raise ValueError("Unsupported student project format")
        archive = self.data.get("archive") if retain else None
        if (
            self.path is None
            and isinstance(archive, dict)
            and isinstance(archive.get("path"), str)
            and isinstance(archive.get("hash"), str)
        ):
            self.path = Path(archive["path"]).resolve()
            self.disk_hash = archive["hash"]
        self.lesson = Lesson.load(self.root / "lesson")
        self.main = resource(self.root, self.data.get("main", ""))
        if not self.main.is_file() or not self.main.is_relative_to(
            self.root / "programs"
        ):
            raise ValueError("The main program must be in programs/")
        self.progress = read_json(self.root / "progress.json")
        if not isinstance(self.progress, dict):
            raise ValueError("Invalid lesson progress")
        stage_ids = {s["id"] for s in self.lesson.stages}
        if (
            not isinstance(self.progress.get("stage"), str)
            or self.progress["stage"] not in stage_ids
        ):
            raise ValueError("Unknown current lesson stage")
        completed = self.progress.get("completed", [])
        if not isinstance(completed, list) or any(
            not isinstance(s, str) or s not in stage_ids for s in completed
        ):
            raise ValueError("Unknown completed lesson stage")
        self.progress["completed"] = list(dict.fromkeys(completed))
        evidence = self.progress.get("evidence", {})
        if not isinstance(evidence, dict) or any(
            key not in stage_ids or value not in ("manual", "devices")
            for key, value in evidence.items()
        ):
            raise ValueError("Invalid task completion evidence")
        self.progress["evidence"] = {
            key: value for key, value in evidence.items() if key in completed
        }
        hints = self.progress.get("hints", {})
        if not isinstance(hints, dict) or any(
            k not in stage_ids or type(v) is not int or v < 0 for k, v in hints.items()
        ):
            raise ValueError("Invalid hint progress")
        starter_files = self.progress.get("starter_files", {})
        if not isinstance(starter_files, dict) or any(
            key not in stage_ids
            or not isinstance(name, str)
            or not name.endswith(".py")
            or resource(self.root / "programs", name).name != name
            for key, name in starter_files.items()
        ):
            raise ValueError("Invalid task starter files")
        mode = self.progress.get("mode", "program")
        if type(mode) is int:
            mode = (
                ("program", "control", "help", "block_editor", "program", "assembly")[
                    mode
                ]
                if 0 <= mode <= 5
                else None
            )
        if mode not in WORKSPACES:
            raise ValueError("Unknown project workspace")
        self.progress["mode"] = mode
        panel = self.progress.get("panel_expanded", self.progress.get("guidance", True))
        if type(panel) is not bool:
            raise ValueError("Invalid task panel state")
        self.progress["panel_expanded"] = panel
        assembly = self.progress.get("assembly", {})
        if (
            not isinstance(assembly, dict)
            or type(assembly.get("step", 0)) is not int
            or assembly.get("step", 0) < 0
        ):
            raise ValueError("Invalid assembly state")
        if "camera" in assembly:
            camera_values(assembly["camera"])
        self.progress.setdefault("completed", [])
        self.progress.setdefault("hints", {})
        current_progress = json.dumps(self.progress, sort_keys=True)
        self.saved_progress = (
            archive["progress"]
            if self.path is not None
            and isinstance(archive, dict)
            and isinstance(archive.get("progress"), str)
            else current_progress
        )
        self.working_progress = current_progress
        self.pending = (
            archive["pending"]
            if self.path is not None
            and isinstance(archive, dict)
            and type(archive.get("pending")) is bool
            else False
        )

    @staticmethod
    def directory():
        root = personal_collection().parent / "projects" / uuid4().hex
        root.mkdir(parents=True)
        return root

    @classmethod
    def attempts(cls, lesson_path: Path | None = None):
        origin = str(lesson_path.resolve()) if lesson_path else None
        parent = personal_collection().parent / "projects"
        candidates = []
        for manifest in parent.glob("*/project.json"):
            try:
                data = read_json(manifest)
                if isinstance(data, dict) and (
                    data.get("template_attempt") is True
                    and isinstance(data.get("id"), str)
                    and isinstance(data.get("origin"), str)
                    and type(data.get("opened")) is int
                    and (origin is None or data.get("origin") == origin)
                ):
                    candidates.append((data.get("opened", 0), manifest.parent))
            except (OSError, ValueError, TypeError):
                continue
        attempts = []
        for _, root in sorted(candidates, reverse=True):
            try:
                attempts.append(cls(root, retain=True))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return attempts

    @classmethod
    def latest(cls, lesson_path: Path):
        return next(iter(cls.attempts(lesson_path)), None)

    def remember_opened(self):
        if self.retain:
            self.data["opened"] = time_ns()
            write_json(self.root / "project.json", self.data)

    def _record_archive(self):
        if not self.retain or self.path is None:
            return
        archive = {
            "path": str(self.path),
            "hash": self.disk_hash,
            "progress": self.saved_progress,
            "pending": self.pending,
        }
        if self.data.get("archive") != archive:
            self.data["archive"] = archive
            write_json(self.root / "project.json", self.data)

    @classmethod
    def create(cls, lesson_path: Path):
        root = cls.directory()
        try:
            if lesson_path.is_dir():
                # Packing also rejects links, keeping imported materials self-contained.
                extract(Lesson.load(lesson_path).archive(), root / "lesson")
            else:
                extract(lesson_path.read_bytes(), root / "lesson")
            lesson = Lesson.load(root / "lesson")
            if lesson.data.get("examples"):
                extract(lesson.archive(), lesson.root)
                lesson = Lesson.load(lesson.root)
            programs = root / "programs"
            programs.mkdir()
            source = (
                resource(lesson.root, lesson.data["starter"]).read_text(
                    encoding="utf-8"
                )
                if "starter" in lesson.data
                else ""
            )
            main = lesson.data.get("main", "main.py")
            for name, origin in lesson.data.get("programs", {}).items():
                destination = resource(programs, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(lesson.file(origin), destination)
            if not (programs / main).exists():
                atomic_write(programs / main, source)
            if "collection" in lesson.data or lesson.data.get("scratch_seeds"):
                collection = (
                    lesson.file(lesson.data["collection"])
                    if "collection" in lesson.data
                    else None
                )
                for program in programs.rglob("*.py"):
                    name = program.relative_to(programs).as_posix()
                    write_json(
                        program.with_suffix(".py.ltr.json"),
                        {
                            "format": 1,
                            "scratch": [
                                lesson.file(fragment).read_text(encoding="utf-8")
                                for fragment in lesson.data.get(
                                    "scratch_seeds", {}
                                ).get(name, [])
                            ],
                            "pins": {},
                            "collections": [
                                Path(
                                    os.path.relpath(collection, program.parent)
                                ).as_posix()
                            ]
                            if collection
                            else [],
                        },
                    )
            created = time_ns()
            write_json(
                root / "project.json",
                {
                    "format": 1,
                    "id": uuid4().hex,
                    "main": "programs/" + main,
                    "origin": str(lesson_path.resolve()),
                    "created": created,
                    "opened": created,
                    "template_attempt": True,
                },
            )
            write_json(
                root / "progress.json",
                {
                    "stage": lesson.stages[0]["id"],
                    "completed": [],
                    "evidence": {},
                    "hints": {},
                    "mode": "program",
                    "panel_expanded": True,
                },
            )
            return cls(root, retain=True)
        except Exception:
            shutil.rmtree(root)
            raise

    @classmethod
    def open(cls, path: Path):
        data = path.read_bytes()
        root = cls.directory()
        try:
            extract(data, root)
            project = cls(root, path, hashlib.sha256(data).hexdigest())
            project.data["template_attempt"] = False
            project.data.pop("archive", None)
            write_json(root / "project.json", project.data)
            return project
        except Exception:
            shutil.rmtree(root)
            raise

    @property
    def stage(self):
        return next(s for s in self.lesson.stages if s["id"] == self.progress["stage"])

    @property
    def score(self):
        completed = set(self.progress["completed"])
        earned = sum(
            stage.get("points", 1)
            for stage in self.lesson.stages
            if stage["id"] in completed
        )
        total = sum(stage.get("points", 1) for stage in self.lesson.stages)
        return earned, total

    @property
    def dirty(self):
        return (
            self.path is None
            or self.pending
            or self.saved_progress != json.dumps(self.progress, sort_keys=True)
        )

    def checkpoint(self):
        progress = json.dumps(self.progress, sort_keys=True)
        if progress != self.working_progress:
            write_json(self.root / "progress.json", self.progress)
            self.working_progress = progress
        self._record_archive()
        return {
            "root": str(self.root),
            "path": str(self.path) if self.path else None,
            "disk_hash": self.disk_hash,
            "saved_progress": self.saved_progress,
            "pending": self.pending,
            "retain": self.retain,
        }

    def portable_snapshot(self):
        manifest = {key: value for key, value in self.data.items() if key != "archive"}
        return pack(
            self.root,
            {"project.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"},
        )

    @classmethod
    def restore(cls, data):
        project = cls(
            Path(data["root"]),
            Path(data["path"]) if data["path"] else None,
            data["disk_hash"],
            retain=data.get("retain", False),
        )
        project.saved_progress = data["saved_progress"]
        project.pending = data.get("pending", False)
        return project

    def save(self, path: Path | None = None):
        destination = path or self.path
        if destination is None:
            raise ValueError("Choose a student project file first")
        destination = destination.resolve()
        if destination.is_relative_to(self.root):
            raise ValueError("Save the archive outside its working directory")
        if destination == self.path:
            current = (
                hashlib.sha256(destination.read_bytes()).hexdigest()
                if destination.exists()
                else None
            )
            if current != self.disk_hash:
                raise ValueError(
                    "Project changed outside LittleTinker Rig; reopen it or save to another path"
                )
        self.checkpoint()
        data = self.portable_snapshot()
        atomic_write(destination, data)
        self.path = destination
        self.disk_hash = hashlib.sha256(data).hexdigest()
        self.saved_progress = json.dumps(self.progress, sort_keys=True)
        self.pending = False
        self._record_archive()

    def discard_working_copy(self):
        parent = personal_collection().parent / "projects"
        if (
            self.root.parent == parent
            and len(self.root.name) == 32
            and all(c in "0123456789abcdef" for c in self.root.name)
        ):
            shutil.rmtree(self.root, ignore_errors=True)

    def export(self, destination, *, snapshot=None, progress=None, cancelled=None):
        """Write an offline copy without changing this project's save baseline."""
        from .ldraw_parts import check_cancelled, resolve_library, subset

        destination = Path(destination).resolve()
        if destination == self.path or destination.is_relative_to(self.root):
            raise ValueError("Export to a separate project file")
        if snapshot is None:
            self.checkpoint()
            snapshot = self.portable_snapshot()
        with TemporaryDirectory(prefix="little-tinker-rig-export-") as temporary:
            root = Path(temporary)
            extract(snapshot, root)
            manifest = read_json(root / "project.json")
            if "archive" in manifest:
                manifest.pop("archive")
                write_json(root / "project.json", manifest)
            lesson = Lesson.load(root / "lesson")
            additions = {}
            if "robot" in lesson.data:
                path = resource(lesson.root, lesson.data["robot"])
                robot = robot_description(path)
                reference = robot.get("library", ".")
                if isinstance(reference, dict):
                    library = resolve_library(
                        path.parent,
                        reference,
                        download=True,
                        progress=progress,
                        cancelled=cancelled,
                    )
                    archive = subset(
                        resource(path.parent, robot["model"]), library, reference
                    )
                    robot["library"] = "offline-parts.zip"
                    number = 1
                    while (path.parent / robot["library"]).exists():
                        robot["library"] = f"offline-parts-{number}.zip"
                        number += 1
                    prefix = path.parent.relative_to(root)
                    additions[(prefix / robot["library"]).as_posix()] = archive
                    additions[path.relative_to(root).as_posix()] = (
                        json.dumps(robot, ensure_ascii=False, indent=2) + "\n"
                    )
            data = pack(root, additions)
            check_cancelled(cancelled)
            atomic_write(destination, data)


def lessons_directory():
    package = Path(__file__).resolve().parents[1]
    bundled = package / "lesson_data"
    return bundled if bundled.is_dir() else package.parent / "lessons"
