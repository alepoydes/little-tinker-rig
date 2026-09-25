import os

import pytest


@pytest.fixture(scope="session")
def qt_app(tmp_path_factory):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    import jedi
    from PySide6.QtWidgets import QApplication

    jedi.settings.cache_directory = str(tmp_path_factory.mktemp("jedi-cache"))
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def interface_language():
    from pyblocks.i18n import DEFAULT_LANGUAGE, language, set_language

    previous = language()
    set_language(DEFAULT_LANGUAGE)
    yield
    set_language(previous)


@pytest.fixture(autouse=True)
def isolated_qt_settings(request, tmp_path, monkeypatch):
    if "qt_app" in request.fixturenames:
        from PySide6.QtCore import QSettings

        import pyblocks.qt.app
        import pyblocks.qt.recovery

        settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(pyblocks.qt.app, "QSettings", lambda *args: settings)
        monkeypatch.setattr(
            pyblocks.qt.recovery, "recovery_directory", lambda: tmp_path / "recovery"
        )
