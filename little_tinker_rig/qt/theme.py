"""Application-owned Qt colors, independent of Python block semantics."""

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

LIGHT = {
    "window": "#f3f6fb",
    "canvas": "#fbfcff",
    "grid": "#e9f0f8",
    "panel": "#ffffff",
    "raised": "#eaf1fa",
    "title": "#edf3fb",
    "rail": "#102947",
    "rail_hover": "#1e4975",
    "rail_selected": "#1268d9",
    "text": "#20334b",
    "muted": "#62768c",
    "border": "#cbd8e6",
    "accent": "#1268d9",
    "accent_text": "#ffffff",
    "hover": "#dfeaf8",
    "selected": "#dbeafe",
    "choice_selected": "#99c9ff",
    "focus": "#176bd9",
    "danger": "#b02a3b",
    "danger_soft": "#ffe1e5",
    "stop": "#d83e50",
    "stop_hover": "#b02a3b",
    "success": "#148357",
    "success_fill": "#148357",
    "link": "#075dbe",
    "code_keyword": "#87439e",
    "code_number": "#a14f17",
    "code_string": "#277a47",
    "code_comment": "#687b90",
    "block_action": "#b8d8ff",
    "block_loop": "#ffda9f",
    "block_control": "#d6c2f5",
    "block_value": "#b9efd0",
    "block_state": "#f7c9a5",
    "block_definition": "#c5d1fa",
    "block_snippet": "#b7e8e2",
    "block_placeholder": "#d9e2ed",
    "block_warning": "#ffc0b4",
}

DARK = {
    "window": "#101b2c",
    "canvas": "#111c2e",
    "grid": "#1b2c42",
    "panel": "#17263c",
    "raised": "#20344e",
    "title": "#0d192a",
    "rail": "#09172a",
    "rail_hover": "#224b75",
    "rail_selected": "#176bd9",
    "text": "#e5efff",
    "muted": "#a6bad2",
    "border": "#36506b",
    "accent": "#4d9fff",
    "accent_text": "#081a2d",
    "hover": "#2a4361",
    "selected": "#25496f",
    "choice_selected": "#24558a",
    "focus": "#76b5ff",
    "danger": "#ff8292",
    "danger_soft": "#5a2636",
    "stop": "#c84157",
    "stop_hover": "#a8324a",
    "success": "#63d8a4",
    "success_fill": "#157452",
    "link": "#8bc6ff",
    "code_keyword": "#cf9af8",
    "code_number": "#ffb57e",
    "code_string": "#8bdba0",
    "code_comment": "#9eb2ca",
    "block_action": "#24588d",
    "block_loop": "#77501d",
    "block_control": "#584487",
    "block_value": "#256d50",
    "block_state": "#70412e",
    "block_definition": "#4d5daa",
    "block_snippet": "#1b6663",
    "block_placeholder": "#425776",
    "block_warning": "#8c404a",
}


def colors(name=None):
    if name is None:
        app = QApplication.instance()
        name = app.property("ltrVisualTheme") if app else "light"
    return DARK if name == "dark" else LIGHT


def theme_name(name):
    return name if name in ("light", "dark") else "light"


def block_color(role):
    """Keep semantic block roles and explicit authored colors independent."""
    palette = colors()
    return QColor(palette.get(f"block_{role}", role))


def svg_icon(name, *, rail=False, tint=None):
    """Tint only the neutral SVG stroke; retain meaningful accent fills."""
    path = Path(__file__).with_name("icons") / f"{name}.svg"
    source = path.read_bytes()
    stroke = tint or ("#ffffff" if rail else colors()["text"])
    source = source.replace(b"#45576b", stroke.encode("ascii"))
    renderer = QSvgRenderer(QByteArray(source))
    icon = QIcon()
    for scale in (1, 2, 3):
        pixmap = QPixmap(24 * scale, 24 * scale)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        # Render into physical pixels before assigning logical high-DPI size.
        # Otherwise QSvgRenderer scales twice and clips the icon at 2x/3x.
        pixmap.setDevicePixelRatio(scale)
        icon.addPixmap(pixmap)
    return icon


def svg_pixmap(name, size, *, tint=None):
    """Render a larger SVG at a fixed logical size on high-DPI displays."""
    path = Path(__file__).with_name("icons") / f"{name}.svg"
    source = path.read_bytes()
    if tint:
        source = source.replace(b"#45576b", tint.encode("ascii"))
    renderer = QSvgRenderer(QByteArray(source))
    scale = 3
    pixmap = QPixmap(size.width() * scale, size.height() * scale)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def contrast_icon(icon):
    """Make monochrome desktop-theme actions legible on the dark toolbar."""
    if colors() is LIGHT:
        return icon
    result = QIcon()
    for scale in (1, 2, 3):
        pixmap = icon.pixmap(QSize(24 * scale, 24 * scale))
        if pixmap.isNull():
            continue
        pixmap.setDevicePixelRatio(scale)
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(colors()["text"]))
        painter.end()
        result.addPixmap(pixmap)
    return result if not result.isNull() else icon


def recolor_document_links(document):
    """Qt Markdown gives anchors a fixed blue that is unreadable on dark pages."""
    color = QColor(colors()["link"])
    block = document.begin()
    while block.isValid():
        fragment = block.begin()
        while not fragment.atEnd():
            item = fragment.fragment()
            if item.isValid() and item.charFormat().anchorHref():
                cursor = QTextCursor(document)
                cursor.setPosition(item.position())
                cursor.setPosition(
                    item.position() + item.length(),
                    QTextCursor.MoveMode.KeepAnchor,
                )
                fmt = item.charFormat()
                fmt.setForeground(color)
                cursor.mergeCharFormat(fmt)
            fragment += 1
        block = block.next()


def apply_application_theme(name):
    """Update shared Qt widget defaults without replacing document widgets."""
    app = QApplication.instance()
    name = theme_name(name)
    if (
        app.property("ltrVisualTheme") == name
        and app.style().objectName().lower() == "fusion"
    ):
        return
    app.setProperty("ltrVisualTheme", name)
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    c = colors(name)
    palette = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "window"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "canvas"),
        (QPalette.ColorRole.AlternateBase, "raised"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "panel"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.Highlight, "accent"),
        (QPalette.ColorRole.HighlightedText, "accent_text"),
        (QPalette.ColorRole.Link, "link"),
        (QPalette.ColorRole.ToolTipBase, "panel"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
    ):
        palette.setColor(role, QColor(c[key]))
    app.setPalette(palette)


def studio_stylesheet(name):
    c = colors(name)
    return f"""
        QMainWindow {{ background: {c['window']}; color: {c['text']}; }}
        QDialog {{ background: {c['window']}; color: {c['text']}; }}
        QFrame#dialogHeader {{ background: {c['accent']};
            border-radius: 9px; }}
        QLabel#dialogHeaderTitle {{ color: {c['accent_text']};
            font-size: 16px; font-weight: 700; }}
        QLabel#dialogHeaderDescription {{ color: {c['accent_text']};
            font-size: 12px; }}
        QFrame#firmwareIdle {{ background: {c['selected']};
            border: 1px solid {c['border']}; border-radius: 9px; }}
        QLabel#firmwareIdleTitle {{ color: {c['accent']};
            font-size: 17px; font-weight: 700; border: 0; }}
        QLabel#firmwareIdleHint {{ color: {c['text']};
            font-size: 12px; border: 0; }}
        QLabel#portLetter {{ background: {c['accent']};
            color: {c['accent_text']}; border-radius: 7px;
            font-size: 14px; font-weight: 700; }}
        QToolBar {{ border: 0; spacing: 6px; padding: 4px 7px;
                    background: {c['window']}; }}
        QToolButton {{ padding: 5px 8px; border-radius: 6px; color: {c['text']}; }}
        QToolButton:hover {{ background: {c['hover']}; }}
        QToolButton:checked {{ background: {c['selected']};
                               border-bottom: 2px solid {c['accent']}; }}
        ChoiceButtons QToolButton:checked {{
            background: {c['choice_selected']};
        }}
        QToolButton:disabled {{ color: {c['muted']}; }}
        ChoiceButtons QToolButton, QToolButton#catalogUtility {{
            padding: 5px 4px;
        }}
        QToolButton#sourceScrollLeft, QToolButton#sourceScrollRight {{
            border: 1px solid {c['border']}; border-radius: 6px;
            padding: 2px; font-size: 17px; font-weight: 700;
        }}
        QToolButton#sourceScrollLeft {{ background: {c['raised']}; }}
        QToolButton#sourceScrollLeft:hover {{ background: {c['hover']}; }}
        QToolButton#sourceScrollRight {{ background: {c['accent']};
            color: {c['accent_text']}; border-color: {c['accent']}; }}
        QToolButton#sourceScrollRight:hover {{ background: {c['focus']}; }}
        QToolButton#sourceScrollLeft:disabled, QToolButton#sourceScrollRight:disabled {{
            background: {c['raised']}; color: {c['muted']};
            border-color: {c['border']};
        }}
        QToolButton#programRun, QToolButton#programStop {{
            border: 1px solid transparent; border-radius: 7px;
            padding: 5px 11px; min-height: 27px; font-weight: 700;
        }}
        QToolButton#programRun {{ background: {c['accent']};
                                  color: {c['accent_text']}; }}
        QToolButton#programRun:hover {{ background: {c['focus']}; }}
        QToolButton#programStop {{ background: {c['stop']}; color: white; }}
        QToolButton#programStop:hover {{ background: {c['stop_hover']}; }}
        QToolButton#programRun:disabled, QToolButton#programStop:disabled {{
            background: {c['raised']}; color: {c['muted']};
            border-color: {c['border']};
        }}
        QToolButton#hubConnection {{ background: {c['panel']};
            border: 1px solid {c['border']}; border-radius: 7px;
            padding: 5px 9px; min-height: 27px; }}
        QToolButton#hubConnection:hover {{ background: {c['hover']}; }}
        QToolButton#hubConnection[connectionState="connected"] {{
            border-color: {c['success']}; }}
        QToolButton#hubConnection[connectionState="busy"] {{
            border-color: {c['accent']}; }}
        QToolButton#appearanceToggle {{ border: 1px solid {c['border']};
            background: {c['panel']}; border-radius: 7px; min-height: 27px; }}
        QToolButton#appearanceToggle:hover {{ background: {c['hover']}; }}
        QTabBar::tab {{ background: {c['raised']}; color: {c['muted']};
            padding: 7px 13px; border: 1px solid {c['border']};
            border-bottom: 0; border-top-left-radius: 6px;
            border-top-right-radius: 6px; margin-right: 3px; }}
        QTabBar::tab:selected {{ background: {c['panel']}; color: {c['text']};
            border-bottom: 2px solid {c['accent']}; }}
        QDockWidget {{ font-weight: bold; color: {c['text']}; }}
        QLineEdit {{ padding: 6px; color: {c['text']};
                     background: {c['panel']}; border: 1px solid {c['border']};
                     border-radius: 5px; }}
        QLineEdit:focus {{ border-color: {c['focus']}; }}
        QDialog QComboBox {{ padding: 6px 8px;
            color: {c['text']}; background: {c['panel']};
            border: 1px solid {c['border']}; border-radius: 6px; }}
        QDialog QComboBox:hover, QDialog QComboBox:focus {{
            border-color: {c['focus']}; }}
        QDialog QComboBox:disabled {{ background: {c['raised']};
            color: {c['muted']}; }}
        QDialog QComboBox QAbstractItemView {{
            background: {c['panel']}; color: {c['text']};
            selection-background-color: {c['selected']};
            selection-color: {c['text']}; }}
        QTreeWidget, QListWidget {{ background: {c['panel']};
                                    color: {c['text']}; border: 0; }}
        QPushButton {{ padding: 6px 10px; color: {c['text']};
                       background: {c['raised']}; border: 1px solid {c['border']};
                       border-radius: 6px; }}
        QPushButton:hover {{ background: {c['hover']}; }}
        QDialog QPushButton#dialogPrimary {{
            background: {c['accent']}; color: {c['accent_text']};
            border-color: {c['accent']}; font-weight: 700;
            padding: 7px 13px; }}
        QDialog QPushButton#dialogPrimary:hover {{ background: {c['focus']}; }}
        QDialog QPushButton#dialogPrimary:disabled {{
            background: {c['raised']}; color: {c['muted']};
            border-color: {c['border']}; }}
        QDialog QPushButton#dialogHelp {{
            background: transparent; color: {c['link']}; border: 0;
            padding: 7px 4px; }}
        QDialog QPushButton#dialogHelp:hover {{
            background: {c['hover']}; text-decoration: underline; }}
        QDialog QPushButton#firmwareLocal {{
            background: {c['selected']}; color: {c['accent']};
            border-color: {c['accent']}; font-weight: 700; }}
        QDialog QPushButton#firmwareLocal:hover {{ background: {c['hover']}; }}
        QDialog QPushButton#firmwareInstall {{
            background: {c['stop']}; color: white;
            border-color: {c['stop']}; font-weight: 700; }}
        QDialog QPushButton#firmwareInstall:hover {{
            background: {c['stop_hover']}; }}
        QDialog QPushButton#firmwareInstall:disabled {{
            background: {c['raised']}; color: {c['muted']};
            border-color: {c['border']}; }}
        QPushButton#assemblyLocal {{ background: {c['selected']};
            color: {c['accent']}; border-color: {c['accent']}; font-weight: 700; }}
        QPushButton#assemblyLocal:hover {{ background: {c['hover']}; }}
        QPushButton#manualStart, QPushButton#blockEditorNew, QPushButton#assemblyRetry {{ background: {c['accent']};
            color: {c['accent_text']}; border-color: {c['accent']};
            font-weight: 700; padding: 8px 12px; }}
        QPushButton#manualStart:hover, QPushButton#blockEditorNew:hover, QPushButton#assemblyRetry:hover {{ background: {c['focus']}; }}
        QPushButton#manualStart:disabled, QPushButton#blockEditorNew:disabled, QPushButton#assemblyRetry:disabled {{ background: {c['raised']};
            color: {c['muted']}; border-color: {c['border']}; }}
        QCheckBox::indicator:unchecked {{ width: 15px; height: 15px;
                                         background: {c['panel']};
                                         border: 1px solid {c['border']};
                                         border-radius: 4px; }}
        QCheckBox::indicator:unchecked:hover {{ border-color: {c['focus']}; }}
        QMenuBar {{ background: transparent; color: {c['text']}; }}
        QMenuBar::item {{ padding: 6px 9px; }}
        QMenuBar::item:selected {{ background: {c['hover']}; border-radius: 5px; }}
        QMenu {{ background: {c['panel']}; color: {c['text']};
                 border: 1px solid {c['border']}; }}
        QMenu::item:selected {{ background: {c['selected']}; }}
        QStatusBar {{ background: {c['title']}; color: {c['muted']}; }}
        QSplitter::handle {{ background: {c['border']}; }}
    """
