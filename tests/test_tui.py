"""Source preservation and hub workflows in the terminal frontend."""

import asyncio
from zipfile import ZipFile

import pytest

from little_tinker_rig.core.source_file import SourceFile


def test_source_saves_preserve_bytes_and_metadata_and_detect_disk_changes(tmp_path):
    path = tmp_path / "main.py"
    raw = "# coding: cp1251\r\n# Привет\r\nvalue =".encode("cp1251")
    path.write_bytes(raw)
    path.chmod(0o640)
    metadata = path.with_suffix(".py.ltr.json")
    metadata.write_text('{"scratch": ["unfinished"]}')
    file = SourceFile(path)
    file.save(file.source)
    assert path.read_bytes() == raw
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
