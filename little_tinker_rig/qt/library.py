"""Compact, colored source previews that remain recognizable after insertion."""

from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QContextMenuEvent,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
)

from little_tinker_rig.core.block_metadata import CATEGORIES
from little_tinker_rig.core.catalog import families
from little_tinker_rig.core.catalog_history import History, reference
from little_tinker_rig.core.expressions import eligible, input_roots
from little_tinker_rig.core.parameters import creation_blocks
from little_tinker_rig.core.presentation import snippet_role
from little_tinker_rig.core.snippets import instantiate
from little_tinker_rig.i18n import N_, tr

from .annotations import block_icon, snippet_title
from .colors import saturated
from .drag import Drag
from .theme import DARK, block_color, colors, svg_icon

IDENTITY = Qt.ItemDataRole.UserRole
PREVIEW = int(IDENTITY) + 1
COLOR = int(IDENTITY) + 2
DESCRIPTION = int(IDENTITY) + 3
ICON = int(IDENTITY) + 4
LEVEL = int(IDENTITY) + 5
DEFINITION = int(IDENTITY) + 6
FAMILY = int(IDENTITY) + 7
VARIANT = int(IDENTITY) + 8
REFERENCE = int(IDENTITY) + 9
ORDER = int(IDENTITY) + 10
FAVORITE = int(IDENTITY) + 11
GROUP_KIND = int(IDENTITY) + 12

CATEGORY_APPEARANCE = {
    "program": ("loop", "▣"),
    "values": ("value", "＝"),
    "data": ("state", "▣"),
    "functions": ("definition", "ƒ"),
    "movement": ("action", "⚙"),
    "input": ("value", "◎"),
    "output": ("control", "✦"),
    "devices": ("snippet", "◇"),
}

LEVEL_TITLES = {
    "beginner": N_("Beginner"),
    "intermediate": N_("Intermediate"),
    "advanced": N_("Advanced"),
    "expert": N_("Expert"),
}


VIEW_TITLES = {
    "catalog": N_("Catalog"),
    "favorites": N_("Favorites"),
    "recent": N_("Recent"),
    "frequent": N_("Frequent"),
    "lesson": N_("For this task"),
}
EMPTY_VIEWS = {
    "favorites": N_("Click a block's star to add it to Favorites."),
    "recent": N_("Inserted blocks will appear here, without duplicates."),
    "frequent": N_("Your most used blocks from the last 30 days will appear here."),
}


def group_title(identity, snippets=()):
    if snippets and snippets[0].group_help:
        return tr(snippets[0].group_help).splitlines()[0]
    return identity


def favorite_rect(rect):
    return QRect(rect.right() - 29, rect.top() + 5, 22, 22)


class CardDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()

    def apply_theme(self):
        self.icons = {
            key: svg_icon(key) for key in ("favorites", "favorite-active")
        }

    def _card_width(self, index):
        view = self.parent()
        depth = 1
        parent = index.parent()
        while parent.isValid():
            depth += 1
            parent = parent.parent()
        return view.viewport().width() - depth * view.indentation()

    @staticmethod
    def _title_lines(index, font, card_width):
        metrics = QFontMetrics(font)
        icon = index.data(ICON) or ""
        icon_width = metrics.horizontalAdvance(icon) + (6 if icon else 0)
        title_width = max(24, card_width - 49 - icon_width)
        title = index.data(DESCRIPTION) or ""
        if metrics.horizontalAdvance(title) <= title_width:
            return icon_width, title_width, [title]
        words = title.split()
        first = []
        for word in words:
            candidate = " ".join((*first, word))
            if metrics.horizontalAdvance(candidate) > title_width:
                break
            first.append(word)
        if not first or len(first) == len(words):
            return icon_width, title_width, [
                metrics.elidedText(title, Qt.TextElideMode.ElideRight, title_width)
            ]
        second = metrics.elidedText(
            " ".join(words[len(first) :]), Qt.TextElideMode.ElideRight, title_width
        )
        return icon_width, title_width, [" ".join(first), second]

    def paint(self, painter, option, index):
        icon = "favorite-active" if index.data(FAVORITE) else "favorites"
        if not index.data(IDENTITY):
            if group := index.data(GROUP_KIND):
                category, nested = group
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                rect = option.rect.adjusted(2, 1, -3, -1)
                selected = bool(option.state & QStyle.StateFlag.State_Selected)
                hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
                if selected or hovered or not nested:
                    background = "selected" if selected else "hover" if hovered else "raised"
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(colors()[background]))
                    painter.drawRoundedRect(rect, 5, 5)
                role, symbol = CATEGORY_APPEARANCE.get(
                    category, ("snippet", "◇")
                )
                accent = block_color(role)
                accent = (
                    accent.lighter(135)
                    if colors() is DARK
                    else saturated(accent, 0.9).darker(135)
                )
                if nested:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(accent)
                    painter.drawEllipse(
                        QRect(rect.left() + 6, rect.center().y() - 3, 6, 6)
                    )
                    label_left = rect.left() + 19
                else:
                    badge = QRect(rect.left() + 3, rect.center().y() - 10, 20, 20)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(accent)
                    painter.drawRoundedRect(badge, 5, 5)
                    painter.setPen(QColor("#ffffff"))
                    painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, symbol)
                    label_left = rect.left() + 29
                font = option.font
                font.setBold(not nested)
                painter.setFont(font)
                painter.setPen(QColor(colors()["text"]))
                painter.drawText(
                    QRect(
                        label_left,
                        rect.top(),
                        max(1, rect.right() - label_left - 4),
                        rect.height(),
                    ),
                    Qt.AlignmentFlag.AlignVCenter,
                    QFontMetrics(font).elidedText(
                        index.data(Qt.ItemDataRole.DisplayRole),
                        Qt.TextElideMode.ElideRight,
                        max(1, rect.right() - label_left - 4),
                    ),
                )
                painter.restore()
                return
            text = QStyleOptionViewItem(option)
            if index.data(REFERENCE):
                text.rect.adjust(0, 0, -30, 0)
            super().paint(painter, text, index)
            if index.data(REFERENCE):
                self.icons[icon].paint(painter, favorite_rect(option.rect))
            return
        painter.save()
        rect = option.rect.adjusted(3, 3, -4, -3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        color = block_color(index.data(COLOR))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        amount = 0.8 if selected else 0.45 if hovered else 0
        dark = colors() is DARK
        painter.setBrush(
            color.lighter(100 + int(amount * 45))
            if dark
            else saturated(color, amount)
        )
        border = (
            color.lighter(175 if selected else 145)
            if dark
            else saturated(color, 0.7 if selected else 0.5)
        )
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 6, 6)
        self.icons[icon].paint(painter, favorite_rect(option.rect))
        painter.setClipRect(rect)
        painter.setPen(QColor(colors()["text"]))
        font = option.font
        font.setBold(True)
        painter.setFont(font)
        icon_width, title_width, lines = self._title_lines(index, font, rect.width())
        line_height = QFontMetrics(font).lineSpacing()
        title_top = rect.top() + 7
        if icon_width:
            painter.drawText(
                QRect(rect.left() + 10, title_top, icon_width, line_height),
                Qt.AlignmentFlag.AlignVCenter,
                index.data(ICON),
            )
        for row, line in enumerate(lines):
            painter.drawText(
                QRect(
                    rect.left() + 10 + icon_width,
                    title_top + row * line_height,
                    title_width,
                    line_height,
                ),
                Qt.AlignmentFlag.AlignVCenter,
                line,
            )
        title_extra = (len(lines) - 1) * line_height
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        variant = index.data(VARIANT)
        if variant:
            painter.drawText(
                rect.adjusted(10, 26 + title_extra, -8, 0),
                Qt.AlignmentFlag.AlignTop,
                QFontMetrics(font).elidedText(
                    variant,
                    Qt.TextElideMode.ElideRight,
                    rect.width() - 20,
                ),
            )
        painter.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        for row, line in enumerate(index.data(PREVIEW).splitlines()[:2]):
            text = painter.fontMetrics().elidedText(
                line, Qt.TextElideMode.ElideRight, rect.width() - 20
            )
            painter.drawText(
                rect.left() + 10,
                rect.top() + 39 + title_extra + bool(variant) * 18 + row * 17,
                text,
            )
        painter.restore()

    def sizeHint(self, option, index):
        if group := index.data(GROUP_KIND):
            return QSize(1, 25 if group[1] else 31)
        if index.data(IDENTITY):
            font = option.font
            font.setBold(True)
            _, _, lines = self._title_lines(index, font, self._card_width(index) - 7)
            return QSize(
                270,
                51
                + (len(lines) - 1) * QFontMetrics(font).lineSpacing()
                + bool(index.data(VARIANT)) * 18
                + 17 * (min(2, len(index.data(PREVIEW).splitlines())) - 1),
            )
        size = super().sizeHint(option, index)
        if index.data(REFERENCE):
            size.setHeight(max(32, size.height()))
        return size


class CardItem(QTreeWidgetItem):
    def __lt__(self, other):
        return (self.data(0, ORDER) or (-1, 0)) < (other.data(0, ORDER) or (-1, 0))


class Library(QTreeWidget):
    insert_requested = Signal()
    definition_requested = Signal(str)
    variants_changed = Signal()
    status_changed = Signal(str)

    def __init__(self, snippets, settings=None):
        super().__init__()
        self.settings = settings
        self.history = History(settings.value("blockLibrary", "") if settings else "")
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setMouseTracking(True)
        self.setIndentation(12)
        self.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(CardDelegate(self))
        self.setMinimumWidth(250)
        self.level = "all"
        self.view = "catalog"
        self.scope = ""
        self.search = ""
        self.context_key = None
        self.eligible_ids = None
        self.stage_ids = None
        self.selected_variants = {}
        self.search_variants = {}
        self.view_states = {}
        self.search_states = {}
        self.rows = {}
        self.headings = {}
        self.empty_message = ""
        self.snapshot = []
        self.favorite_press = None
        self.group_press = None
        self._card_layout_pending = False
        self.currentItemChanged.connect(lambda *_: self.variants_changed.emit())
        self.itemDoubleClicked.connect(lambda *_: self.insert_requested.emit())
        self.load(snippets)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (
            event.size().width() != event.oldSize().width()
            and not self._card_layout_pending
        ):
            self._card_layout_pending = True
            QTimer.singleShot(0, self, self._relayout_cards)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.empty_message:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.viewport().rect()
        text_width = max(1, bounds.width() - 32)
        font = self.font()
        font.setPointSize(max(9, font.pointSize()))
        painter.setFont(font)
        flags = Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap
        text_height = QFontMetrics(font).boundingRect(
            QRect(0, 0, text_width, max(1, bounds.height())),
            flags,
            self.empty_message,
        ).height()
        group_height = 54 + text_height
        top = max(12, (bounds.height() - group_height) // 3)
        badge = QRect(bounds.center().x() - 22, top, 44, 44)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors()["accent"]))
        painter.drawEllipse(badge)
        icon = self.view if self.view in VIEW_TITLES else "catalog"
        svg_icon(icon, rail=True).paint(
            painter, QRect(badge.left() + 10, badge.top() + 10, 24, 24)
        )
        painter.setPen(QColor(colors()["text"]))
        painter.drawText(
            QRect(16, badge.bottom() + 10, text_width, text_height + 4),
            flags,
            self.empty_message,
        )
        painter.end()

    def _relayout_cards(self):
        self._card_layout_pending = False
        option = QStyleOptionViewItem()
        option.font = self.font()
        delegate = self.itemDelegate()
        for item in self.rows.values():
            if item.data(0, IDENTITY):
                index = self.indexFromItem(item)
                item.setSizeHint(0, delegate.sizeHint(option, index))
        self.doItemsLayout()

    def remember_view(self):
        item = self.currentItem()
        self.view_states[self.view] = (
            item.data(0, REFERENCE) if item else None,
            self.verticalScrollBar().value(),
            {key: heading.isExpanded() for key, heading in self.headings.items()},
        )

    def load(self, snippets):
        self.remember_view()
        self.snippets = {s.identity: s for s in snippets if not s.historical}
        self.families = {f.identity: f for f in families(snippets)}
        self.context_key = None
        self.eligible_ids = None
        self.function_key = self.functions_key(snippets)
        self.render()

    @staticmethod
    def functions_key(snippets):
        return tuple(
            (s.identity, s.parameters, s.help)
            for s in snippets
            if s.identity.startswith("document/")
        )

    def render(self):
        selected, scroll, expanded = self.view_states.get(self.view, (None, 0, {}))
        self.blockSignals(True)
        self.clear()
        self.rows, self.headings = {}, {}
        if self.view in ("catalog", "lesson"):
            grouped = {}
            for family in self.families.values():
                grouped.setdefault(family.category, []).append(family)
            for category in (*CATEGORIES, *(k for k in grouped if k not in CATEGORIES)):
                members = grouped.get(category, ())
                if not members:
                    continue
                title = (
                    tr(CATEGORIES[category])
                    if category in CATEGORIES
                    else group_title(category, (members[0].primary,))
                )
                heading = QTreeWidgetItem(self, [title])
                heading.setData(0, GROUP_KIND, (category, False))
                heading.setToolTip(0, category)
                heading.setFlags(heading.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                heading.setExpanded(expanded.get(category, self.level == "beginner"))
                self.headings[category] = heading
                for family in members:
                    parent = heading
                    path = category
                    for segment in family.primary.group:
                        path += "/" + segment
                        if path not in self.headings:
                            child = CardItem(parent, [tr(segment)])
                            child.setData(0, GROUP_KIND, (category, True))
                            child.setData(0, ORDER, (-1, len(self.headings)))
                            child.setFlags(
                                child.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                            )
                            child.setExpanded(
                                expanded.get(path, self.level == "beginner")
                            )
                            self.headings[path] = child
                        parent = self.headings[path]
                    self.add_family(family, parent)
        else:
            refs = self.history.favorites if self.view == "favorites" else self.snapshot
            for key in refs:
                entry = self.history.entries.get(key)
                if entry is None:
                    continue
                family = self.families.get(entry["identity"])
                if family and key == reference(family.identity, self.scope):
                    self.add_family(family, self)
                elif self.view == "favorites":
                    item = QTreeWidgetItem(self, [tr(entry["title"]).splitlines()[0]])
                    item.setData(0, REFERENCE, key)
                    item.setData(0, FAVORITE, True)
                    item.setToolTip(
                        0,
                        tr(
                            "This favorite is unavailable in the current document or collections."
                        )
                        + "\n"
                        + entry["identity"]
                        + "\n"
                        + entry["scope"],
                    )
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                    item.setForeground(0, QColor(colors()["muted"]))
                    self.rows[key] = item
        self.blockSignals(False)
        self.filter(self.search)
        if selected in self.rows and not self.rows[selected].isHidden():
            self.setCurrentItem(self.rows[selected])
        self.verticalScrollBar().setValue(scroll)
        self.variants_changed.emit()

    def add_family(self, family, parent):
        item = CardItem(parent)
        key = reference(family.identity, self.scope)
        item.setData(0, FAMILY, family.identity)
        item.setData(0, REFERENCE, key)
        self.rows[key] = item
        self.paint_variant(item, family.primary)

    def paint_variant(self, item, snippet):
        family = self.families[snippet.catalog_id]
        preview = instantiate(
            snippet, {p.name: p.name for p in snippet.parameters if p.default is None}
        ).source
        item.setText(0, snippet_title(family.primary))
        for role, value in (
            (IDENTITY, snippet.identity),
            (ICON, block_icon(snippet)),
            (LEVEL, snippet.level),
            (PREVIEW, preview),
            (COLOR, snippet_role(snippet)),
            (DESCRIPTION, snippet_title(family.primary)),
            (DEFINITION, snippet.definition),
            (VARIANT, tr(snippet.variant) if snippet.variant else ""),
            (FAVORITE, item.data(0, REFERENCE) in self.history.favorites),
        ):
            item.setData(0, role, value)
        item.setToolTip(
            0,
            tr(LEVEL_TITLES[snippet.level])
            + "\n"
            + preview
            + "\n\n"
            + tr(snippet.help),
        )

    def update_functions(self, snippets):
        if self.functions_key(snippets) != self.function_key:
            self.load(snippets)
            return True
        return False

    def set_scope(self, scope):
        scope = str(scope.resolve()) if isinstance(scope, Path) else scope
        if scope != self.scope:
            self.remember_view()
            self.scope = scope
            self.render()

    def set_view(self, view):
        if view not in VIEW_TITLES:
            return
        self.remember_view()
        self.view = view
        self.read_history()
        self.snapshot = (
            self.history.frequent() if view == "frequent" else list(self.history.recent)
        )
        self.render()

    def read_history(self):
        if self.settings is not None:
            self.history = History(self.settings.value("blockLibrary", ""))

    def mutate_history(self, operation, *args):
        self.read_history()
        result = getattr(self.history, operation)(*args)
        if self.settings is not None:
            self.settings.setValue("blockLibrary", self.history.dumps())
        return result

    def relocate_scope(self, before, after):
        self.remember_view()
        moved = self.mutate_history("relocate_scope", before, after)
        self.snapshot = [moved.get(key, key) for key in self.snapshot]
        self.view_states = {
            view: (moved.get(key, key), scroll, expanded)
            for view, (key, scroll, expanded) in self.view_states.items()
        }
        self.search_states = {
            view: (expanded, moved.get(key, key), scroll)
            for view, (expanded, key, scroll) in self.search_states.items()
        }
        if self.scope == before:
            self.scope = after
        self.render()

    def record_use(self, identity):
        snippet = self.snippets.get(identity)
        if snippet is None:
            return
        primary = self.families[snippet.catalog_id].primary
        title = primary.help or primary.identity
        self.mutate_history("use", primary.identity, self.scope, title)
        # Frequent is a snapshot until the user enters that view again.
        if self.view == "recent":
            self.set_view(self.view)

    def toggle_favorite(self):
        item = self.currentItem()
        if item is None:
            return
        key = item.data(0, REFERENCE)
        if family := self.families.get(item.data(0, FAMILY)):
            primary = family.primary
            title = primary.help or primary.identity
            self.mutate_history("favorite", family.identity, self.scope, title)
        elif key in self.history.entries:
            entry = self.history.entries[key]
            self.mutate_history(
                "favorite", entry["identity"], entry["scope"], entry["title"]
            )
        if self.view == "favorites":
            self.remember_view()
            self.render()
        else:
            item.setData(0, FAVORITE, key in self.history.favorites)
        self.variants_changed.emit()

    def expand_groups(self, expand):
        for heading in self.headings.values():
            heading.setExpanded(expand)
        self.remember_view()

    def move_favorite(self, offset):
        item = self.currentItem()
        if item and item.data(0, REFERENCE) in self.history.favorites:
            self.mutate_history("move", item.data(0, REFERENCE), offset)
            self.remember_view()
            self.render()

    def clear_history(self):
        self.mutate_history("clear_recent" if self.view == "recent" else "reset_usage")
        self.set_view(self.view)

    def allowed(self):
        if self.view == "lesson":
            return self.stage_ids if self.stage_ids is not None else frozenset()
        return None

    def choices(self, family):
        return family.choices(
            "all" if self.view == "lesson" else self.level,
            self.allowed(),
            self.eligible_ids,
        )

    def current_choices(self):
        item = self.currentItem()
        family = self.families.get(item.data(0, FAMILY)) if item else None
        return self.choices(family) if family else ()

    def select_variant(self, identity):
        item = self.currentItem()
        for snippet in self.current_choices():
            if snippet.identity == identity:
                self.selected_variants[snippet.catalog_id] = identity
                if self.search:
                    self.search_variants[snippet.catalog_id] = identity
                self.paint_variant(item, snippet)
                self.variants_changed.emit()
                return

    def search_rank(self, family, words, members=None):
        if not words:
            return 0
        members = family.members if members is None else members
        texts = (
            " ".join(
                snippet_title(s)
                + " "
                + (s.help.splitlines()[0] if s.help else "")
                + " "
                + tr(s.variant or "")
                for s in members
            ),
            " ".join(s.identity for s in members),
            tr(CATEGORIES.get(family.category, family.category))
            + " "
            + " ".join(tr(part) + " " + part for part in family.primary.group)
            + " "
            + " ".join(s.help + " " + tr(s.help) for s in members),
            " ".join(s.definition for s in members),
        )
        combined = ""
        for rank, text in enumerate(texts):
            combined += " " + text.casefold()
            if all(word in combined for word in words):
                return rank
        return None

    def filter(self, search, level=None):
        previous_search = self.search
        changed_level = level is not None and level != self.level
        if level is not None:
            self.level = level
        if search and (not previous_search or self.view not in self.search_states):
            current = self.currentItem()
            self.search_states[self.view] = (
                {k: v.isExpanded() for k, v in self.headings.items()},
                current.data(0, REFERENCE) if current else None,
                self.verticalScrollBar().value(),
            )
        expanded, selected, scroll = self.search_states.get(self.view, ({}, None, 0))
        if search != previous_search:
            self.search_variants.clear()
        self.search = search
        words = search.casefold().split()
        hidden, visible = 0, 0
        for position, item in enumerate(self.rows.values()):
            family = self.families.get(item.data(0, FAMILY))
            if family is None:
                item.setHidden(
                    not all(
                        word in (item.text(0) + " " + item.toolTip(0)).casefold()
                        for word in words
                    )
                )
                visible += not item.isHidden()
                continue
            choices = self.choices(family)
            rank = self.search_rank(family, words, choices)
            match = rank is not None and bool(choices)
            item.setHidden(not match)
            relevant = tuple(
                s
                for s in family.members
                if self.eligible_ids is None or s.identity in self.eligible_ids
            )
            hidden += (
                not match
                and bool(relevant)
                and self.search_rank(family, words, relevant) is not None
            )
            visible += match
            item.setData(0, ORDER, (rank if rank is not None else 99, position))
            if choices:
                wanted = self.selected_variants.get(family.identity)
                snippet = next((s for s in choices if s.identity == wanted), choices[0])
                if (
                    words
                    and self.search_variants.get(family.identity) != snippet.identity
                ):

                    def priority(choice, family=family, wanted=wanted):
                        score = self.search_rank(family, words, (choice,))
                        return (
                            score if score is not None else 99,
                            choice.identity != wanted,
                        )

                    snippet = min(choices, key=priority)
                if item.data(0, IDENTITY) != snippet.identity:
                    self.paint_variant(item, snippet)
        for key, group in reversed(self.headings.items()):
            group.setHidden(
                all(group.child(i).isHidden() for i in range(group.childCount()))
            )
            if words:
                group.setExpanded(True)
            elif previous_search:
                group.setExpanded(expanded.get(key, False))
            elif changed_level:
                group.setExpanded(self.level == "beginner")
        # Reorder only search results; personal views retain their own order.
        if (search or previous_search) and self.headings:
            for group in self.headings.values():
                group.sortChildren(0, Qt.SortOrder.AscendingOrder)
        item = self.currentItem()
        if item and item.isHidden():
            self.setCurrentItem(None)
        if previous_search and not search:
            if selected in self.rows and not self.rows[selected].isHidden():
                self.setCurrentItem(self.rows[selected])
                self.verticalScrollBar().setValue(scroll)
            self.search_states.pop(self.view, None)
        if self.view == "lesson" and self.stage_ids is None:
            status = tr("Open a lesson to see blocks suggested for the current task.")
        elif not visible:
            status = (
                tr("No blocks match these filters.")
                if words or hidden
                else tr(EMPTY_VIEWS.get(self.view, "No blocks match these filters."))
            )
        else:
            status = ""
        if hidden and (words or self.view == "favorites" or self.context_key):
            status += ("\n" if status else "") + tr(
                "{count} matching families hidden by level, task or selected input.",
                count=hidden,
            )
        self.empty_message = status if not visible else ""
        self.setAccessibleDescription(self.empty_message)
        self.viewport().update()
        self.status_changed.emit(status)
        self.variants_changed.emit()

    def set_context(self, session, slot=None, providers=False):
        key = (
            session.document.syntax,
            session.editor.selection,
            session.visible_matches,
        )
        if key == self.context_key:
            return
        self.context_key = key
        if providers:
            self.eligible_ids = {
                s.identity
                for s in creation_blocks(
                    self.snippets.values(), slot.parameter.annotation
                )
            }
            self.filter(self.search)
            return
        inputs = input_roots(session)
        self.eligible_ids = {
            s.identity for s in self.snippets.values() if eligible(session, s, inputs)
        }
        self.filter(self.search)

    def clear_context(self):
        self.context_key = self.eligible_ids = None
        self.filter(self.search)

    def mimeData(self, items):
        data = QMimeData()
        if items and items[0].data(0, IDENTITY):
            data.setData(
                "application/x-little-tinker-rig-snippet",
                items[0].data(0, IDENTITY).encode(),
            )
        return data

    def startDrag(self, actions):
        item = self.currentItem()
        if item and item.data(0, IDENTITY):
            Drag(
                self,
                self.mimeData([item]),
                self.viewport().grab(self.visualItemRect(item)),
            )

    def favorite_at(self, point):
        item = self.itemAt(point)
        if (
            item
            and item.data(0, REFERENCE)
            and favorite_rect(self.visualItemRect(item)).contains(point)
        ):
            return item

    def mousePressEvent(self, event):
        self.favorite_press = None
        self.group_press = None
        if event.button() == Qt.MouseButton.LeftButton:
            point = event.position().toPoint()
            if item := self.favorite_at(point):
                self.favorite_press = item.data(0, REFERENCE)
                self.setCurrentItem(item)
                event.accept()
                return
            item = self.itemAt(point)
            if item and item.data(0, GROUP_KIND):
                self.group_press = (item, point, item.isExpanded())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.favorite_press:
            event.accept()
            return
        if self.group_press and (
            event.position().toPoint() - self.group_press[1]
        ).manhattanLength() > QApplication.startDragDistance():
            self.group_press = None
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.favorite_press and event.button() == Qt.MouseButton.LeftButton:
            key, self.favorite_press = self.favorite_press, None
            item = self.favorite_at(event.position().toPoint())
            if item and item.data(0, REFERENCE) == key:
                self.setCurrentItem(item)
                self.toggle_favorite()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        pressed, self.group_press = self.group_press, None
        if pressed and event.button() == Qt.MouseButton.LeftButton:
            item, _, was_expanded = pressed
            if self.itemAt(event.position().toPoint()) is item:
                # Qt already toggles its disclosure arrow; the rest of the row
                # should have the same one-click behavior.
                if item.isExpanded() == was_expanded:
                    item.setExpanded(not was_expanded)
                event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.favorite_at(event.position().toPoint()):
            self.mousePressEvent(event)
            return
        if (item := self.itemAt(event.position().toPoint())) and item.data(
            0, GROUP_KIND
        ):
            self.group_press = None
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            if item := self.favorite_at(event.pos()):
                QToolTip.showText(
                    event.globalPos(),
                    tr(
                        "Remove from Favorites"
                        if item.data(0, FAVORITE)
                        else "Add to Favorites"
                    ),
                    self.viewport(),
                    favorite_rect(self.visualItemRect(item)),
                )
                return True
        return super().viewportEvent(event)

    def context_menu(self, item):
        from PySide6.QtWidgets import QMenu

        if item is None or not item.data(0, REFERENCE):
            return
        self.setCurrentItem(item)
        menu = QMenu(self)
        choices = self.current_choices()
        if len(choices) > 1:
            variants = menu.addMenu(tr("Variant"))
            variants.setToolTipsVisible(True)
            variant_group = QActionGroup(variants)
            for snippet in choices:
                action = variants.addAction(
                    tr(snippet.variant) if snippet.variant else snippet_title(snippet)
                )
                action.setCheckable(True)
                variant_group.addAction(action)
                action.setChecked(snippet.identity == item.data(0, IDENTITY))
                action.setData(snippet.identity)
                action.setToolTip(tr(snippet.help))
                action.triggered.connect(
                    lambda checked=False, identity=snippet.identity: self.select_variant(
                        identity
                    )
                )
        favorite = item.data(0, REFERENCE) in self.history.favorites
        menu.addAction(
            tr("Remove from Favorites" if favorite else "Add to Favorites"),
            self.toggle_favorite,
        )
        if self.view == "favorites":
            menu.addAction(tr("Move up"), lambda: self.move_favorite(-1))
            menu.addAction(tr("Move down"), lambda: self.move_favorite(1))
        if identity := item.data(0, IDENTITY):
            menu.addAction(
                tr("Open definition"), lambda: self.definition_requested.emit(identity)
            )
        return menu

    def keyPressEvent(self, event):
        item = self.currentItem()
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and item
            and item.data(0, IDENTITY)
        ):
            self.insert_requested.emit()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        keyboard = event.reason() == QContextMenuEvent.Reason.Keyboard
        item = self.currentItem() if keyboard else self.itemAt(event.pos())
        if menu := self.context_menu(item):
            point = (
                self.viewport().mapToGlobal(self.visualItemRect(item).center())
                if keyboard
                else event.globalPos()
            )
            menu.exec(point)
            menu.deleteLater()
