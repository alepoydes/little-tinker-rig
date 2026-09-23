import os

import pytest


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def interface_language():
    from pyblocks.i18n import DEFAULT_LANGUAGE, language, set_language

    previous = language()
    set_language(DEFAULT_LANGUAGE)
    yield
    set_language(previous)
