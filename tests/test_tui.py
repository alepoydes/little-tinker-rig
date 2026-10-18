"""Source preservation and hub workflows in the terminal frontend."""

import asyncio
from zipfile import ZipFile

import pytest

from little_tinker_rig.core.source_file import SourceFile


@pytest.fixture(autouse=True)
def isolate_tui_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "little_tinker_rig.tui.recovery.recovery_directory",
        lambda: tmp_path / "tui-recovery",
    )


def test_utf8_saves_preserve_drafts_newlines_metadata_and_detect_disk_changes(tmp_path):
    path = tmp_path / "main.py"
    raw = "# coding: cp1251\r\n# Привет\r\nvalue =".encode("cp1251")
    path.write_bytes(raw)
    path.chmod(0o640)
    metadata = path.with_suffix(".py.ltr.json")
    metadata.write_text('{"scratch": ["unfinished"]}')
    file = SourceFile(path)
    file.save(file.source)
    expected = "# coding: utf-8\r\n# Привет\r\nvalue ="
    assert path.read_bytes() == expected.encode("utf-8")
    assert file.source == SourceFile(path).source == expected
    assert not file.dirty(expected)
    assert path.stat().st_mode & 0o777 == 0o640
    assert metadata.read_text() == '{"scratch": ["unfinished"]}'
    path.write_bytes(b"external change")
    with pytest.raises(ValueError, match="outside"):
        file.save("value = 1")
    assert path.read_bytes() == b"external change"
    new = tmp_path / "copy.py"
    new.write_bytes(b"important")
    with pytest.raises(FileExistsError):
        file.save("value = 2", new)
    assert file.path == path and new.read_bytes() == b"important"
    file.save("value = 2", new, overwrite=True)
    assert file.path == new and not file.dirty("value = 2")


async def until(predicate):
    async with asyncio.timeout(8):
        while not predicate():
            await asyncio.sleep(0.02)


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "#!/usr/bin/python\r\n# -*- coding: cp1251 -*-\r\nx =",
            "#!/usr/bin/python\r\n# -*- coding: utf-8 -*-\r\nx =",
        ),
        ("\n# coding=latin-1\nx =", "\n# coding=utf-8\nx ="),
        ('value = """\n# coding: latin-1\n"""', 'value = """\n# coding: latin-1\n"""'),
        (
            "# comment\n# comment\n# coding: cp1251\nx =",
            "# comment\n# comment\n# coding: cp1251\nx =",
        ),
        ("\ufeff# coding: utf-8\nx =", "# coding: utf-8\nx ="),
    ],
)
def test_source_save_normalizes_only_python_encoding_declarations(
    tmp_path, source, expected
):
    file = SourceFile()
    file.save(source, tmp_path / "main.py")
    assert file.path.read_bytes() == expected.encode("utf-8")
    assert file.source == SourceFile(file.path).source == expected


async def test_tui_save_updates_encoding_cookie_and_keeps_undo(tmp_path):
    from little_tinker_rig.tui.app import Studio

    path = tmp_path / "main.py"
    source = "# coding: cp1251\r\n# Привет\r\nvalue ="
    path.write_bytes(source.encode("cp1251"))
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.editor.move_cursor((2, 7))
        await pilot.press("ctrl+s")
        await until(lambda: app.file.encoding == "utf-8")
        assert app.editor.text == app.file.source == source.replace("cp1251", "utf-8")
        assert app.editor.cursor_location == (2, 7)
        assert not app.file.dirty(app.editor.text)
        await pilot.press("ctrl+z")
        assert app.editor.text == source and app.file.dirty(app.editor.text)
        await pilot.press("ctrl+s")
        await until(lambda: not app.file.dirty(app.editor.text))
        assert SourceFile(path).source == app.editor.text


async def test_tui_unfinished_source_save_search_undo_and_discard(tmp_path):
    from textual.widgets import Input

    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.dialogs import Unsaved

    path = tmp_path / "main.py"
    path.write_text("# comment\nx =")
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.editor.is_syntax_aware
        app.editor.move_cursor((1, 3))
        await pilot.press("end", "4", "ctrl+s")
        await until(lambda: path.read_text().endswith("4"))
        app.editor.load_text('name = "name"\n')
        await pilot.press("ctrl+f")
        app.query_one("#find", Input).value = "name"
        app.query_one("#replacement", Input).value = "other"
        await pilot.click("#replace-all")
        assert app.editor.text == 'other = "other"\n'
        app.editor.focus()
        await pilot.press("ctrl+z")
        assert app.editor.text == 'name = "name"\n'
        await pilot.press("ctrl+q")
        await until(lambda: isinstance(app.screen, Unsaved))
        await pilot.click("#cancel")
        assert app.editor.text == 'name = "name"\n'
        await pilot.press("ctrl+q")
        await until(lambda: isinstance(app.screen, Unsaved))
        await pilot.click("#discard")
    assert path.read_text() == "# comment\nx =4"
    assert not app.robot.thread.is_alive()


async def test_reopen_current_file_reads_after_save_confirmation(tmp_path):
    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.dialogs import Form, Unsaved

    path = tmp_path / "main.py"
    path.write_text("value = 1\n")
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        app.editor.load_text("value = 2\n")
        await pilot.press("ctrl+o")
        await until(lambda: isinstance(app.screen, Form))
        await pilot.click("#accept")
        await until(lambda: isinstance(app.screen, Unsaved))
        await pilot.click("#save")
        await until(lambda: not isinstance(app.screen, (Form, Unsaved)))
        await until(lambda: not app.file.dirty(app.editor.text))
        assert app.editor.text == path.read_text() == "value = 2\n"
        app.editor.load_text("value = 3\n")
        await pilot.press("ctrl+s")
        await until(lambda: path.read_text() == "value = 3\n")


async def test_tui_virtual_upload_run_error_location_and_explicit_monitor(tmp_path):
    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.dialogs import Form

    path = tmp_path / "robot.py"
    path.write_text('print("hello")\nprint(1 / 0)\n')
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        await asyncio.wrap_future(app.robot.connect_hub(transport="virtual"))
        await until(lambda: app.info.connected)
        await pilot.press("f4")
        await until(lambda: app.robot.stored_program is not None and not app.hub_busy)
        assert not app.info.running and not app.query_one("#ports").display
        app.action_run_stored()
        await until(lambda: app.problem is not None)
        assert app.problem.path == path and app.problem.line == 2
        assert any("hello" in line for line in app.output_log.lines)
        app.action_error()
        await until(lambda: app.editor.cursor_location[0] == 1)
        await pilot.press("f9")
        await until(lambda: isinstance(app.screen, Form))
        assert not app.query_one("#ports").display
        await pilot.click("#accept")
        await until(lambda: app.info.monitoring and app.ports.row_count > 0)
        await pilot.press("f6")
        await until(lambda: not app.hub_busy and not app.query_one("#ports").display)
        app.action_disconnect()
        await until(lambda: not app.info.connected)
    assert not app.robot.thread.is_alive()


async def test_tui_runs_unsaved_editor_snapshot_without_overwriting_file(tmp_path):
    from little_tinker_rig.tui.app import Studio

    path = tmp_path / "robot.py"
    path.write_text('print("saved")\n', encoding="utf-8")
    app = Studio(path)
    async with app.run_test(size=(120, 40)) as pilot:
        await asyncio.wrap_future(app.robot.connect_hub(transport="virtual"))
        await until(lambda: app.info.connected)
        app.editor.load_text('print("draft")\nprint(1 / 0)\n')
        path.write_text('print("external")\n', encoding="utf-8")
        await pilot.press("f5")
        await until(lambda: app.robot.stored_program is not None and not app.hub_busy)
        await until(lambda: any("draft" in line for line in app.output_log.lines))
        assert (
            app.robot.stored_program.sources[path] == 'print("draft")\nprint(1 / 0)\n'
        )
        assert app.recovery.path.exists()
        assert path.read_text(encoding="utf-8") == 'print("external")\n'
        assert app.file.dirty(app.editor.text)
        await until(lambda: app.problem is not None)
        app.action_error()
        await until(lambda: app.editor.cursor_location[0] == 1)


async def test_tui_runs_untitled_snapshot_and_navigates_its_error(
    tmp_path, monkeypatch
):
    from little_tinker_rig.tui.app import Studio

    monkeypatch.chdir(tmp_path)
    app = Studio()
    async with app.run_test(size=(120, 40)) as pilot:
        await asyncio.wrap_future(app.robot.connect_hub(transport="virtual"))
        await until(lambda: app.info.connected)
        app.editor.load_text('print("untitled")\nprint(1 / 0)\n')
        await pilot.press("f4")
        await until(lambda: app.robot.stored_program is not None and not app.hub_busy)
        assert app.file.path is None
        assert not (tmp_path / "untitled.py").exists()
        await pilot.press("f5")
        await until(lambda: app.problem is not None)
        assert app.file.path is None
        assert not (tmp_path / "untitled.py").exists()
        assert app.problem.path == tmp_path / "untitled.py"
        app.action_error()
        await until(lambda: app.editor.cursor_location[0] == 1)


def test_tui_recovery_skips_live_sessions_and_preserves_disk_conflicts(tmp_path):
    from little_tinker_rig.tui.recovery import Recovery

    path = tmp_path / "main.py"
    path.write_text("saved = True\n", encoding="utf-8")
    file = SourceFile(path)
    first = Recovery()
    second = Recovery()
    first.flush(file, "draft = True\n", (0, 5))
    assert list(second.stale()) == []
    first.close(remove=False)
    stale = list(second.stale())
    assert [candidate for candidate, _ in stale] == [first.path]
    for _, lock in stale:
        Recovery.release(lock)
    restored, text, cursor = Recovery.read(first.path)
    assert text == "draft = True\n" and cursor == (0, 5)
    path.write_text("external = True\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        restored.save(text)
    assert path.read_text(encoding="utf-8") == "external = True\n"


async def test_tui_restores_draft_after_unclean_close(tmp_path):
    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.dialogs import RecoveryPrompt, Unsaved

    path = tmp_path / "main.py"
    path.write_text("saved = True\n", encoding="utf-8")
    first = Studio(path)
    async with first.run_test(size=(120, 40)):
        first.editor.load_text("draft = True\n")
        await until(lambda: first.recovery.path.exists())
        assert first.recovery.path.exists()
    assert first.recovery.path.exists()
    second = Studio(path)
    async with second.run_test(size=(120, 40)) as pilot:
        await until(lambda: isinstance(second.screen, RecoveryPrompt))
        await pilot.click("#later")
        await until(lambda: not isinstance(second.screen, RecoveryPrompt))
        assert first.recovery.path.exists()
        await pilot.pause()
        second.offer_recovery()
        await until(lambda: isinstance(second.screen, RecoveryPrompt))
        await pilot.click("#restore")
        await until(lambda: second.editor.text == "draft = True\n")
        assert second.file.path == path and second.file.dirty(second.editor.text)
        assert path.read_text(encoding="utf-8") == "saved = True\n"
        assert second.recovery.path.exists() and not first.recovery.path.exists()
        await pilot.press("ctrl+q")
        await until(lambda: isinstance(second.screen, Unsaved))
        await pilot.click("#discard")
    assert not second.recovery.path.exists()


@pytest.mark.parametrize("key", ["f4", "f5"])
async def test_tui_transfer_stops_if_draft_cannot_be_recovered(
    tmp_path, monkeypatch, key
):
    from little_tinker_rig.tui.app import Studio

    app = Studio(tmp_path / "main.py")
    async with app.run_test(size=(120, 40)) as pilot:
        await asyncio.wrap_future(app.robot.connect_hub(transport="virtual"))
        await until(lambda: app.info.connected)
        app.editor.load_text("print('draft')\n")

        def fail(*args):
            raise OSError("checkpoint failed")

        monkeypatch.setattr(app.recovery, "flush", fail)
        await pilot.press(key)
        await until(
            lambda: any("checkpoint failed" in line for line in app.output_log.lines)
        )
        assert app.robot.stored_program is None


async def test_tui_completion_replaces_token_and_progress_is_visible(tmp_path):
    from textual import events
    from textual.widgets import OptionList

    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.editor import Completions

    app = Studio(tmp_path / "main.py")
    async with app.run_test(size=(120, 40)) as pilot:
        source = "items = []\nitems.appBAD"
        app.editor.load_text(source)
        app.editor.move_cursor((1, 9))
        await pilot.press("ctrl+space")
        await until(lambda: isinstance(app.screen, Completions))
        await pilot.pause()
        choices = app.screen.query_one(OptionList)
        choices.highlighted = next(
            i
            for i in range(choices.option_count)
            if choices.get_option_at_index(i).id == "append"
        )
        await pilot.press("enter")
        await until(lambda: app.editor.text.endswith("items.append"))
        app.hub_busy = True
        app.post_message(events.Print("Uploading: 63%\r", stderr=True))
        await until(lambda: app.progress.progress == 63)
        assert any("63%" in line for line in app.output_log.lines)


async def test_tui_firmware_review_invalidation_and_isolated_install(
    tmp_path, monkeypatch
):
    import json

    from textual.widgets import Checkbox, Input, Select

    from little_tinker_rig.tui.app import Studio
    from little_tinker_rig.tui.firmware import FirmwareScreen

    path = tmp_path / "firmware.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr("firmware-base.bin", b"\0" * 1024)
        archive.writestr(
            "firmware.metadata.json",
            json.dumps(
                {
                    "metadata-version": "2.1.0",
                    "firmware-version": "test",
                    "device-id": 0x81,
                    "checksum-type": "none",
                    "checksum-size": 1024,
                    "hub-name-offset": 0,
                    "hub-name-size": 0,
                }
            ),
        )
        archive.writestr("ReadMe_OSS.txt", "Test firmware license")
    monkeypatch.setattr(
        "little_tinker_rig.tui.firmware.firmware_cache", lambda: tmp_path
    )
    calls, processes = [], []

    class Process:
        def __init__(self):
            self.stdout = asyncio.StreamReader()
            self.stdout.feed_data(b"100%\n")

        async def wait(self):
            return 0

    async def spawn(*args, **kwargs):
        calls.append(args)
        process = Process()
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    app = Studio()
    async with app.run_test(size=(120, 45)) as pilot:
        app.action_firmware()
        await until(lambda: isinstance(app.screen, FirmwareScreen))
        await pilot.pause()
        screen = app.screen
        from little_tinker_rig.pybricks.firmware import Image

        screen.images = [
            Image("inventor", "pybricks", "4.0.1", ""),
            Image(
                "inventor",
                "pybricks",
                "4.1.0b4",
                "",
                channel="beta",
                notes="https://github.com/pybricks/pybricks-micropython/releases/tag/v4.1.0b4",
            ),
        ]
        screen.selection_changed()
        assert screen.query_one("#channel", Select).value == "stable"
        assert screen.query_one("#version", Select).value == "0"
        screen.package = object()
        screen.query_one("#consent", Checkbox).value = True
        screen.query_one("#channel", Select).value = "beta"
        await pilot.pause()
        assert screen.query_one("#version", Select).value == "1"
        assert (
            screen.package is None and not screen.query_one("#consent", Checkbox).value
        )
        assert not screen.query_one("#notes").disabled
        screen.query_one("#local-path", Input).value = str(path)
        await pilot.click("#local")
        await until(lambda: screen.package is not None and not screen.busy)
        digest = screen.package.digest
        assert not calls
        screen.query_one("#consent", Checkbox).value = True
        await pilot.pause()
        await pilot.click("#install")
        await until(lambda: bool(calls))
        await pilot.press("escape", "ctrl+q")
        assert app.screen is screen and screen.busy
        processes[0].stdout.feed_eof()
        await until(lambda: not screen.busy)
        assert calls[0][2:4] == ("-m", "little_tinker_rig.pybricks.firmware")
        assert digest in calls[0]
        assert any(
            "completed" in line for line in screen.query_one("#firmware-log").lines
        )
        assert not screen.query_one("#consent", Checkbox).value
        screen.query_one("#kind", Select).value = "lego"
        await until(lambda: screen.package is None)
        await pilot.press("escape")
