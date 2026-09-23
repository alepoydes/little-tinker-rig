"""Qt payload for an in-process, revision-checked structural transfer."""

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag


class BlockMime(QMimeData):
    def __init__(self, transfer):
        super().__init__()
        self.transfer = transfer
        self.setData("application/x-pyblocks-fragment", transfer.text.encode())
        self.setText(transfer.text)


def drag_block(widget, transfer):
    drag = QDrag(widget)
    drag.setMimeData(BlockMime(transfer))
    pixmap = widget.grab()
    if pixmap.width() > 360:
        pixmap = pixmap.scaledToWidth(360, Qt.TransformationMode.SmoothTransformation)
    drag.setPixmap(pixmap)
    return drag.exec(Qt.DropAction.MoveAction)
