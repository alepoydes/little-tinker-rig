"""Compact, colored source previews that remain recognizable after insertion."""

from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QContextMenuEvent,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
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
from little_tinker_rig.core.presentation import role_color, snippet_role
from little_tinker_rig.core.snippets import instantiate
from little_tinker_rig.i18n import N_, tr

from .annotations import block_icon, snippet_title
from .colors import saturated
from .drag import Drag

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
        self.icons = {
            key: QIcon(str(Path(__file__).with_name("icons") / f"{key}.svg"))
            for key in ("favorites", "favorite-active")
        }

    def paint(self, painter, option, index):
        icon = "favorite-active" if index.data(FAVORITE) else "favorites"
        if not index.data(IDENTITY):
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
        color = QColor(index.data(COLOR))
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setBrush(saturated(color, 0.8 if selected else 0.45 if hovered else 0))
        painter.setPen(QPen(QColor("#c5d1da"), 1))
        painter.drawRoundedRect(rect, 6, 6)
        self.icons[icon].paint(painter, favorite_rect(option.rect))
        painter.setClipRect(rect)
        painter.setPen(QColor("#203040"))
        description = index.data(ICON) + "  " + index.data(DESCRIPTION)
        font = option.font
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(10, 7, -32, 0),
            Qt.AlignmentFlag.AlignTop,
            QFontMetrics(font).elidedText(
                description, Qt.TextElideMode.ElideRight, rect.width() - 44
            ),
        )
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        variant = index.data(VARIANT)
        if variant:
            painter.drawText(
                rect.adjusted(10, 26, -8, 0),
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
                rect.left() + 10, rect.top() + 39 + bool(variant) * 18 + row * 17, text
            )
        painter.restore()

    def sizeHint(self, option, index):
        if index.data(IDENTITY):
            return QSize(
                270,
                51
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
        self.setMinimumWidth(270)
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
        self.snapshot = []
        self.favorite_press = None
        self.currentItemChanged.connect(lambda *_: self.variants_changed.emit())
        self.itemDoubleClicked.connect(lambda *_: self.insert_requested.emit())
        self.load(snippets)

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
                    item.setForeground(0, QColor("#6b7785"))
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
            (COLOR, role_color(snippet_role(snippet))),
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
        if event.button() == Qt.MouseButton.LeftButton:
            if item := self.favorite_at(event.position().toPoint()):
                self.favorite_press = item.data(0, REFERENCE)
                self.setCurrentItem(item)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.favorite_press:
            event.accept()
            return
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

    def mouseDoubleClickEvent(self, event):
        if self.favorite_at(event.position().toPoint()):
            self.mousePressEvent(event)
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
