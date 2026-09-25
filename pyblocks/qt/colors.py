"""Activity changes chroma, never stacks a dark overlay on structural colors."""

from PySide6.QtGui import QColor


def saturated(color, amount):
    hue, saturation, lightness, alpha = QColor(color).getHslF()
    return QColor.fromHslF(
        hue, saturation + (1 - saturation) * amount, lightness, alpha
    )
