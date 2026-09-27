"""Resolve focus before painting: stronger color with one bounded lightness change."""

from PySide6.QtGui import QColor


def saturated(color, amount):
    hue, saturation, lightness, alpha = QColor(color).getHslF()
    # Pastels reach maximum saturation before focus becomes conspicuous. Lower
    # lightness in this same transform, never by multiplying an extra overlay.
    return QColor.fromHslF(
        hue,
        saturation + (1 - saturation) * amount,
        lightness - 0.18 * amount,
        alpha,
    )
