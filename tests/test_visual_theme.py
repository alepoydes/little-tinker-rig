"""Theme assets retain their geometry on high-density displays."""

from PySide6.QtCore import QSize

from little_tinker_rig.qt.theme import svg_icon


def test_svg_icon_is_not_clipped_at_high_dpi(qt_app):
    icon = svg_icon("program")
    for scale in (1, 2, 3):
        pixmap = icon.pixmap(QSize(24, 24), float(scale))
        image = pixmap.toImage()
        visible = [
            (x, y)
            for y in range(image.height())
            for x in range(image.width())
            if image.pixelColor(x, y).alpha() > 20
        ]
        assert pixmap.devicePixelRatio() == scale
        assert pixmap.width() == pixmap.height() == 24 * scale
        assert visible
        assert min(x for x, _ in visible) >= 3 * scale
        assert max(x for x, _ in visible) <= 21 * scale
        assert min(y for _, y in visible) >= scale
        assert max(y for _, y in visible) <= 23 * scale
