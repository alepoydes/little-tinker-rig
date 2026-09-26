"""Translate authored widget captions without rebuilding editors or losing undo.

Capture static captions once. Dynamic data is rendered explicitly with tr();
editable text and filenames are never extracted as user interface captions.
"""

from PySide6.QtCore import QLibraryInfo, QObject, QTranslator
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLabel,
    QMenu,
    QTableWidget,
)

from pyblocks.i18n import language, tr

_qt_translation = None


def translate_standard_dialogs():
    global _qt_translation
    app = QApplication.instance()
    if _qt_translation is not None:
        app.removeTranslator(_qt_translation)
        _qt_translation.deleteLater()
    _qt_translation = QTranslator(app)
    if _qt_translation.load(
        "qtbase_" + language(),
        QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
    ):
        app.installTranslator(_qt_translation)


def localize(root):
    items = [root, *root.findChildren(QObject)]
    for item in items:
        sources = item.property("translationSources")
        if sources is None:
            properties = [
                "windowTitle",
                "toolTip",
                "statusTip",
                "placeholderText",
                "accessibleName",
            ]
            if isinstance(item, (QLabel, QAbstractButton, QAction)):
                properties.append("text")
            if isinstance(item, QMenu):
                properties.append("title")
            sources = {
                name: item.property(name)
                for name in properties
                if item.metaObject().indexOfProperty(name) >= 0 and item.property(name)
            }
            if isinstance(item, QComboBox) and not item.isEditable():
                sources["items"] = [item.itemText(i) for i in range(item.count())]
            if isinstance(item, QTableWidget):
                sources["headers"] = [
                    item.horizontalHeaderItem(i).text()
                    for i in range(item.columnCount())
                ]
            if getattr(item, "translate_tabs", False):
                sources["tabs"] = [item.tabText(i) for i in range(item.count())]
            item.setProperty("translationSources", sources)
    for item in items:
        sources = item.property("translationSources")
        for name, source in sources.items():
            if name == "items":
                for index, text in enumerate(source):
                    item.setItemText(index, tr(text))
            elif name == "headers":
                item.setHorizontalHeaderLabels([tr(text) for text in source])
            elif name == "tabs":
                for index, text in enumerate(source):
                    item.setTabText(index, tr(text))
                    item.setTabToolTip(index, tr(text))
                item.updateGeometry()
            else:
                item.setProperty(name, tr(source))
