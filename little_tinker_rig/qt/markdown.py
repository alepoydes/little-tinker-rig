"""Shared sizing for local images in Help and lesson task Markdown."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextCursor, QTextDocument


def fit_images(browser):
    document = browser.document()
    images = []
    block = document.begin()
    while block.isValid():
        fragment = block.begin()
        while not fragment.atEnd():
            text = fragment.fragment()
            if text.charFormat().isImageFormat():
                images.append((text.position(), text.charFormat().toImageFormat()))
            fragment += 1
        block = block.next()
    for position, fmt in images:
        source = document.resource(
            QTextDocument.ResourceType.ImageResource, QUrl(fmt.name())
        )
        if source is None or source.width() <= 0:
            continue
        width = min(
            source.width(),
            max(1, browser.viewport().width() - 2 * document.documentMargin() - 4),
        )
        if fmt.width() == width:
            continue
        fmt.setWidth(width)
        fmt.setHeight(width * source.height() / source.width())
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.movePosition(
            QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.setCharFormat(fmt)
