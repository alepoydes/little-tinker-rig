"""Contours belong to logical blocks and leave source/layout geometry intact."""

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QPainterPath

from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import builtin_snippets
from little_tinker_rig.qt.editor import SourceView


def test_sibling_cards_are_separate_and_comments_belong_inside(
    qt_app, monkeypatch
):
    session = Session.fragment(
        "print(1)\nprint(2)\nwhile True:\n    print(3)\n", builtin_snippets()
    )
    view = SourceView(session)
    view.resize(900, 600)
    view.show()
    qt_app.processEvents()
    try:
        original = session.document.state
        rectangles = tuple(view._rect(line, 0) for line in range(1, 5))
        owners = {r.line: r for r in view.presentation if r.outlined}
        first = view.outline_path(owners[1], 1, 4)
        second = view.outline_path(owners[2], 1, 4)
        assert first.boundingRect().bottom() < second.boundingRect().top()
        assert first.contains(view.note_rect(1, 0).center())
        assert second.contains(view.note_rect(2, 0).center())
        assert not first.contains(view.note_rect(2, 0).center())
        boundary = second.boundingRect().top()
        x = int(second.boundingRect().right() - 25)
        colored = view.viewport().grab().toImage()
        point = QPointF(x, boundary).toPoint()
        assert colored.pixelColor(point) != colored.pixelColor(x, point.y() + 3)
        # Turning off only contour paint must not alter text, row heights or hit tests.
        monkeypatch.setattr(view, "outline_path", lambda *_: QPainterPath())
        plain = view.viewport().grab().toImage()
        assert colored.pixelColor(point) != plain.pixelColor(point)
        assert tuple(view._rect(line, 0) for line in range(1, 5)) == rectangles
        assert session.document.state is original
    finally:
        view.close()


def test_source_gutter_stays_outside_hit_area_after_theme_refresh(qt_app):
    session = Session.fragment(
        "".join(f"print({index})\n" for index in range(1, 31)),
        builtin_snippets(),
    )
    view = SourceView(session)
    view.resize(500, 240)
    view.show()
    qt_app.processEvents()
    try:
        for _ in range(2):
            view.apply_theme()
            qt_app.processEvents()
            assert view.gutter.geometry().right() < view.viewport().geometry().left()
            for line in (1, 2):
                point = view._rect(line, 0).center().toPoint()
                assert view.source_line_at(point) == line
        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
        qt_app.processEvents()
        assert view.source_line_at(QPoint(4, 4)) > 2
    finally:
        view.close()
