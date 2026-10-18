"""Capture localized documentation screenshots from isolated Qt workspaces.

Run on a desktop with the Qt extra installed. Assembly also needs the official
LDraw archive already downloaded through the app. Captures go to a review folder;
copy approved images into doc/<language>/images/ after visual inspection.
"""

import argparse
import json
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

import little_tinker_rig.core.paths as paths
import little_tinker_rig.qt.app as desktop
import little_tinker_rig.qt.recovery as recovery
from little_tinker_rig.i18n import set_language
from little_tinker_rig.qt.theme import colors

ROOT = Path(__file__).resolve().parents[1]
SIZES = (1600, 850)


def wait_for(predicate, app, seconds=30):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(100)
    raise TimeoutError("The documentation capture did not reach its expected state")


def capture(output, language, name, app, widget):
    app.processEvents()
    QTest.qWait(200)
    path = output / language / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not widget.grab().save(str(path)):
        raise OSError(f"Could not save {path}")
    print(path, flush=True)


def capture_assembly(output, app, window):
    """Replace only Qt's uncapturable native child with its actual GL frame."""
    page = window.lessons.assembly
    wait_for(lambda: page.scene is not None and page.view is not None, app, 60)
    page.set_step(4)
    window.lessons.set_panel_expanded(False)
    QTest.qWait(150)
    page.reset_camera()
    QTest.qWait(450)
    view = page.view
    scale = view.devicePixelRatio()
    width = round(view.width() * scale)
    height = round(view.height() * scale)
    view.makeCurrent()
    frame = view.renderer.ctx.simple_framebuffer((width, height), components=4)
    view.renderer.draw(
        frame,
        view.camera,
        view.step,
        selected=view.selection,
        future=view.future,
        group=view.group,
        size=(width, height),
        background=QColor(colors()["canvas"]).getRgbF(),
    )
    pixels = frame.read(components=4, alignment=1)
    image = (
        QImage(pixels, width, height, width * 4, QImage.Format.Format_RGBA8888)
        .flipped(Qt.Orientation.Vertical)
        .copy()
    )
    frame.release()
    view.doneCurrent()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(scale)
    replacement = QLabel()
    replacement.setPixmap(pixmap)
    replacement.setScaledContents(True)
    page.view_host.layout().replaceWidget(page.view_container, replacement)
    page.view_container.hide()
    capture(output, "en", "assembly", app, window)
    window.change_language("ru")
    capture(output, "ru", "assembly", app, window)


def capture_language(output, app, window, code):
    window.change_language(code)
    window.set_mode(5)
    capture(output, code, "home", app, window)

    window.lessons.open(ROOT / "lessons/first_python")
    window.set_mode(0)
    window.lessons.set_panel_expanded(True)
    capture(output, code, "editor", app, window)

    window.document_page.change_mode(1)
    capture(output, code, "python-editor", app, window)
    window.document_page.change_mode(0)

    window.lessons.show_stage()
    capture(output, code, "help", app, window)


def capture_reference(output, app, window, code, program):
    window.change_language(code)
    window.open_document(program)
    window.set_mode(0)
    window.level_filter.select("all")
    window.library.collapseAll()
    window.library.headings["movement"].setExpanded(True)
    for group in ("movement/Individual motors", "movement/Individual motors/Setup"):
        window.library.headings[group].setExpanded(True)
    window.library.scrollToTop()
    capture(output, code, "library", app, window.library_pane)

    source = window.document_page.text
    window.session.editor.select(source.index("motor.run_angle"))
    window.source.refresh_source()
    from little_tinker_rig.qt.variants import VariantDialog

    dialog = VariantDialog(window.source)
    choice = next(
        (
            index
            for index in range(dialog.variant.count())
            if dialog.variants[dialog.variant.itemData(index)].variant
            == "Choose stop behavior and waiting"
        ),
        -1,
    )
    if choice < 0:
        raise ValueError(
            "The expected motor variant is unavailable: "
            + repr(
                [
                    dialog.variants[dialog.variant.itemData(index)].variant
                    for index in range(dialog.variant.count())
                ]
            )
        )
    dialog.variant.setCurrentIndex(choice)
    dialog.preview_toggle.setChecked(True)
    dialog.show()
    capture(output, code, "block-variants", app, dialog)
    dialog.close()
    dialog.deleteLater()

    definition = next(
        snippet
        for snippet in window.session.available_snippets
        if snippet.source_path and "motor_target" in snippet.identity
    )
    window.open_definition(definition)
    capture(output, code, "block-editor", app, window)

    window.set_mode(0)
    robot = window._robot()
    if not window.hub_info.connected:
        robot.connect_hub(transport="virtual", model="inventor")
        wait_for(
            lambda: window.hub_info.monitoring and not window.hub_is_busy,
            app,
            30,
        )
    window.set_mode(1)
    capture(output, code, "controls", app, window)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="review directory for PNG files")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    model_root = ROOT / "lessons/first_drive/robot"
    specification = json.loads((model_root / "robot.json").read_text(encoding="utf-8"))
    archive = paths.parts_cache() / (specification["library"]["sha256"] + ".zip")
    if not archive.is_file():
        raise FileNotFoundError(
            "Open First drive assembly once in the app to cache its LDraw archive"
        )

    with TemporaryDirectory(prefix="ltr-doc-capture-") as temporary:
        temporary_root = Path(temporary)
        cache_root = temporary_root / "cache"
        ldraw_root = cache_root / "ldraw"
        ldraw_root.mkdir(parents=True)
        (ldraw_root / archive.name).symlink_to(archive)
        scenes = ldraw_root / "scenes"
        scenes.mkdir()
        for cached in (archive.parent / "scenes").glob("*.npz"):
            (scenes / cached.name).symlink_to(cached)
        paths.user_cache_path = lambda *args, **kwargs: cache_root
        from little_tinker_rig.core.ldraw_parts import resolve_library

        resolved = resolve_library(model_root, specification["library"], download=False)
        assert resolved == ldraw_root / archive.name
        app = QApplication([])
        program = temporary_root / "boost_sequence.py"
        shutil.copyfile(ROOT / "examples/boost_sequence.py", program)

        def workspace(name):
            root = temporary_root / name
            paths.user_data_path = lambda *args, **kwargs: root / "data"
            desktop.QSettings = lambda *args: QSettings(
                str(root / "settings.ini"), QSettings.Format.IniFormat
            )
            recovery.recovery_directory = lambda: root / "recovery"
            set_language(name if name in ("en", "ru") else "en")
            window = desktop.Studio()
            window.resize(*SIZES)
            window.show()
            QTest.qWait(250)
            return window

        for code in ("en", "ru"):
            window = workspace(code)
            try:
                capture_language(output, app, window, code)
                capture_reference(output, app, window, code, program)
                window.disconnect_hub()
                wait_for(lambda current=window: not current.hub_info.connected, app)
            finally:
                window.recovery.close()
                window.close()

        window = workspace("assembly")
        try:
            window.lessons.open(ROOT / "lessons/first_drive")
            showcase = (ROOT / "lessons/first_drive/setup.py").read_text(
                encoding="utf-8"
            ) + (
                "\ndrive.straight(200)\n"
                "drive.turn(90)\n"
                "drive.straight(-200)\n"
                "drive.brake()\n"
            )
            window.session.editor.commit(showcase)
            window.refresh_views()
            window.lessons.select_stage(3)
            window.set_mode(0)
            window.view_filter.select("lesson")
            window.lessons.set_panel_expanded(True)
            capture(output, "en", "showcase", app, window)
            window.lessons.select_stage(0)
            window.lessons.open_assembly()
            capture_assembly(output, app, window)
        finally:
            window.recovery.close()
            window.close()
        manifest = {
            "purpose": "Documentation screenshots of current Qt UI",
            "languages": ["en", "ru"],
            "window": list(SIZES),
            "platform": app.platformName(),
            "device_pixel_ratio": app.primaryScreen().devicePixelRatio(),
        }
        (output / "capture.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
