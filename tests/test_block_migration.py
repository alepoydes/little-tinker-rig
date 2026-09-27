import ast
import tomllib

from little_tinker_rig.cli.main import main
from little_tinker_rig.core.migration import migrate_collection
from little_tinker_rig.core.snippets import instantiate, load_collection


def legacy_collection(root):
    (root / "collection.toml").write_text("""# A teaching collection.
[collection]
id = "course"
version = "2"
  format = 1 # Legacy templates.
[levels]
"motion/create" = "standard" # Public name.
"motion/move" = "beginner"
[[history]]
version = "1"
path = "history/v1"
""")
    (root / "motion.py").write_text('''"""Motion. Course examples."""
def create(name=device, port=1):
    """Name a device."""
    # Keep authored comments.
    name = dict(port=port)

def move(device=device, speed: "deg/s" = 90):
    """Set a speed."""
    device["speed"] = speed
''')
    history = root / "history/v1"
    history.mkdir(parents=True)
    (history / "motion.py").write_text(
        'def move(device=device, speed=90):\n    device["old_speed"] = speed\n'
    )
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_cli_migration_preserves_expansion_history_and_is_explicit(tmp_path, capsys):
    original = legacy_collection(tmp_path)
    before = load_collection(tmp_path)
    assert main(["migrate-blocks", str(tmp_path)]) == 0
    assert "+@inline_block" in capsys.readouterr().out
    assert all(
        (tmp_path / name).read_bytes() == data for name, data in original.items()
    )
    assert main(["migrate-blocks", str(tmp_path), "--write"]) == 0
    manifest = tomllib.loads((tmp_path / "collection.toml").read_text())
    assert manifest["collection"]["format"] == 2
    assert "levels" not in manifest
    assert "# Public name." in (tmp_path / "collection.toml").read_text()
    assert "# Keep authored comments." in (tmp_path / "motion.py").read_text()
    assert (tmp_path / "history/v1/motion.py").read_bytes() == original[
        "history/v1/motion.py"
    ]
    after = load_collection(tmp_path)
    assert len(before) == len(after)
    for old, new in zip(before, after, strict=True):
        assert (old.identity, old.version, old.historical) == (
            new.identity,
            new.version,
            new.historical,
        )
        if not old.historical:
            assert old.level == new.level
        old_code, new_code = instantiate(old, {}), instantiate(new, {})
        assert ast.dump(ast.parse(old_code.source)) == ast.dump(
            ast.parse(new_code.source)
        )
        assert old_code.imports == new_code.imports
    assert all(s.mode == "inline" for s in after if not s.historical)
    assert migrate_collection(tmp_path) == {}


def test_migration_validation_precedes_writes(tmp_path, capsys):
    original = legacy_collection(tmp_path)
    broken = tmp_path / "motion.py"
    broken.write_text(broken.read_text() + "\ndef broken(\n")
    original["motion.py"] = broken.read_bytes()
    assert main(["migrate-blocks", str(tmp_path), "--write"]) == 2
    assert "never closed" in capsys.readouterr().err
    assert all(
        (tmp_path / name).read_bytes() == data for name, data in original.items()
    )


def test_migration_restores_written_modules_on_manifest_failure(
    tmp_path, monkeypatch, capsys
):
    from little_tinker_rig.core import project

    original = legacy_collection(tmp_path)
    write = project.atomic_write

    def fail_manifest(path, text, encoding="utf-8"):
        if path.name == "collection.toml":
            raise OSError("disk full")
        write(path, text, encoding)

    monkeypatch.setattr(project, "atomic_write", fail_manifest)
    assert main(["migrate-blocks", str(tmp_path), "--write"]) == 2
    assert "disk full" in capsys.readouterr().err
    assert all(
        (tmp_path / name).read_bytes() == data for name, data in original.items()
    )
