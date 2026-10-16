from little_tinker_rig.core.catalog_history import reference
from little_tinker_rig.core.parameters import change_parameter, choices, slots
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import Parameter, load_module


def test_measurement_suggestions_preserve_dependencies_and_undo(tmp_path, qt_app):
    from little_tinker_rig.core.variants import variant_bindings, variant_source

    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.hubs import PrimeHub\n"
        "from pybricks.pupdevices import Motor\n"
        "from pybricks.parameters import Port\n"
        "hub = PrimeHub()\nmotor = Motor(Port.A)\nmotor.run_angle(300, 90)\n"
    )
    session = Session(path)
    slot = next(s for s in slots(session) if s.parameter.name == "angle")
    options = choices(session, slot.parameter, slot.span.start)
    assert "motor.angle()" in options
    assert not any("run_until_stalled" in value for value in options)
    value = "hub.imu.rotation(Axis.X)"
    assert value in options
    before = session.document.state
    change_parameter(session, slot, value)
    assert "from pybricks.parameters import Axis" in session.document.state.source
    assert session.document.state.source.endswith(f"motor.run_angle(300, {value})\n")
    assert not session.analysis.diagnostics()
    session.editor.undo()
    assert session.document.state is before

    session.editor.selection = session.document.syntax.tree.body[-1]
    match = session.selected_match()
    values = variant_bindings(session, match, match.snippet)
    values["angle"] = value
    candidate = variant_source(session, match, match.snippet, values)
    assert "from pybricks.parameters import Axis" in candidate
    assert session.document.state is before

    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.variants import VariantDialog

    view = SourceView(session)
    dialog = VariantDialog(view)
    try:
        field = dialog.fields["angle"]
        field.setCurrentIndex(field.findText(value))
        field.setEditText("hub.imu.rotation(Axis.Y)")
        assert dialog.update_preview()
        assert "from pybricks.parameters import Axis" in dialog.candidate
        target = next(
            s
            for s in dialog.variants.values()
            if "rotation_angle" in {p.name for p in s.parameters}
        )
        dialog.variant.setCurrentIndex(dialog.variant.findData(target.identity))
        assert (
            dialog.fields["rotation_angle"].currentText() == "hub.imu.rotation(Axis.Y)"
        )
        assert "from pybricks.parameters import Axis" in dialog.candidate
        dialog.apply()
        assert not session.analysis.diagnostics()
        session.editor.undo()
        assert session.document.state is before
    finally:
        dialog.close()
        view.close()


def test_nested_receiver_contract_keeps_outer_linked_edit(tmp_path, qt_app):
    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.structure import block_menu

    path = tmp_path / "main.py"
    path.write_text("force = sensor.force()\n")
    session = Session(path)
    view = SourceView(session)
    view.show()
    qt_app.processEvents()
    try:
        slot = next(
            s
            for s in view.parameter_slots
            if session.document.syntax.text(s.node) == "sensor"
        )
        assert slot.parameter.annotation == "ForceSensor"
        menu = block_menu(view, view.parameter_rect(slot).center().toPoint())
        assert "Find creation blocks" in [a.text() for a in menu.actions()]
        menu.deleteLater()
        before = session.document.state
        change_parameter(session, slot, "force_sensor")
        assert session.document.state.source == "force = force_sensor.force()\n"
        session.editor.undo()
        assert session.document.state is before
    finally:
        view.close()


def test_scratch_search_survives_catalog_focus_and_applies_to_origin(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nmotor = Motor(Port.A)\n"
    )
    window = Studio(path)
    window.show()
    try:
        window.level_filter.select("all")
        window.session.set_scratch(None, "motor.run(300)\n")
        window.refresh_views()
        window.scratch_dock.show()
        window.scratch_dock.raise_()
        qt_app.processEvents()
        view = window.scratch.cells[0].source
        view.setFocus()
        slot = next(s for s in view.parameter_slots if s.parameter.name == "speed")
        view.search_input(slot)
        window.search.setFocus()
        qt_app.processEvents()
        assert window.input_search == (view, slot)
        window.library.setCurrentItem(
            window.library.rows[reference("pybricks/motors/motor_speed")]
        )
        window.library.setFocus()
        qt_app.processEvents()
        before = window.session.document.state
        window.insert_selected()
        assert window.session.document.state.source == before.source
        assert window.session.document.state.scratch == ("motor.run(motor.speed())\n",)
        assert window.input_search is None
        window.session.editor.undo()
        assert window.session.document.state is before
    finally:
        window.confirm_close = lambda *_: True
        window.close()


def test_filled_drop_requires_search_for_that_exact_input(tmp_path, qt_app):
    from PySide6.QtCore import QMimeData, QPointF, Qt
    from PySide6.QtGui import (
        QDragEnterEvent,
        QDragLeaveEvent,
        QDragMoveEvent,
        QDropEvent,
    )

    from little_tinker_rig.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nmotor = Motor(Port.A)\nmotor.run(300)\nmotor.run(500)\n"
    )
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    view = window.source
    data = QMimeData()
    data.setData(
        "application/x-little-tinker-rig-snippet", b"pybricks/motors/motor_speed"
    )

    def hover(slot):
        point = view.parameter_rect(slot).center().toPoint()
        qt_app.sendEvent(
            view.viewport(),
            QDragEnterEvent(
                point,
                Qt.DropAction.CopyAction,
                data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        point = view.parameter_rect(slot).center().toPoint()
        event = QDragMoveEvent(
            point,
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        qt_app.sendEvent(view.viewport(), event)
        return event.isAccepted(), point

    try:
        window.level_filter.select("all")
        first, second = [s for s in view.parameter_slots if s.parameter.name == "speed"]
        assert not hover(first)[0]
        qt_app.sendEvent(view.viewport(), QDragLeaveEvent())
        view.search_input(first)
        assert not hover(second)[0]
        qt_app.sendEvent(view.viewport(), QDragLeaveEvent())
        accepted, point = hover(first)
        assert accepted
        before = window.session.document.state
        drop = QDropEvent(
            QPointF(point),
            Qt.DropAction.CopyAction,
            data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        qt_app.sendEvent(view.viewport(), drop)
        assert drop.isAccepted()
        assert window.session.document.state.source.endswith(
            "motor.run(motor.speed())\nmotor.run(500)\n"
        )
        window.session.editor.undo()
        assert window.session.document.state is before
    finally:
        window.confirm_close = lambda *_: True
        window.close()


def test_providers_are_results_and_public_declarations_not_consumers():
    snippets = load_module(
        """
@inline_block(names=("name",))
def create(name=thing):
    name: "Motor" = Motor()

@inline_block
def value() -> "Motor":
    return Motor()

@block
def private(motor: "Motor" = motor):
    hidden: "Motor" = Motor()
    motor.stop()
""",
        "test/providers",
        "1",
    )
    assert [s.produced_types for s in snippets] == [("Motor",), ("Motor",), ()]


def test_unit_suggestions_exclude_unknown_reporters_but_allow_python_names(tmp_path):
    path = tmp_path / "motor.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nmotor = Motor(Port.A)\nspeed = 300\nmotor.run(speed)\n"
    )
    session = Session(path)
    values = choices(
        session,
        Parameter("speed", None, "number[deg/s]"),
        path.read_text().index("motor.run"),
    )
    assert {"speed", "motor.speed()"} <= set(values)
    assert "motor.load()" not in values
    assert "motor.angle()" not in values


def test_pinned_provider_search_keeps_variants_restrictions_and_restores_catalog(
    tmp_path, qt_app
):
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import IDENTITY

    path = tmp_path / "main.py"
    path.write_text("sensor.force()\n")
    window = Studio(path)
    window.show()
    qt_app.processEvents()
    try:
        window.level_filter.select("all")
        window.search.setText("wait")
        previous = window.session.document.state
        slot = next(
            s for s in window.source.parameter_slots if s.parameter.name == "sensor"
        )
        window.source.search_input(slot, True)
        card = window.library.rows[reference("pybricks/sensors/create_color_sensor")]
        assert card.data(0, IDENTITY) == "pybricks/sensors/create_force_sensor"
        assert not card.isHidden()
        assert window.library.headings["input"].isExpanded()
        assert not any(
            s.identity.endswith("/run_motor")
            for s in window.library.snippets.values()
            if s.identity in window.library.eligible_ids
        )
        window.source.session.editor.select(0)
        window.refresh_status()
        assert window.whole_blocks.isVisible()
        assert window.session.document.state is previous
        window.library.lesson_ids = frozenset({"pybricks/sensors/create_color_sensor"})
        window.library.filter("")
        assert card.isHidden()
        window.library.lesson_ids = None
        window.clear_input_search()
        assert window.search.text() == "wait"
        assert window.library.eligible_ids is None
        window.search.clear()
        window.source.search_input(slot, True)
        window.session.editor.commit("force = 0\n")
        window.refresh_views()
        assert window.input_search is None
    finally:
        window.confirm_close = lambda *_: True
        window.close()


def test_nested_search_restores_branches_and_flat_personal_view(tmp_path, qt_app):
    from PySide6.QtCore import QSettings

    from little_tinker_rig.core.snippets import builtin_snippets
    from little_tinker_rig.qt.library import Library

    library = Library(
        builtin_snippets(),
        QSettings(str(tmp_path / "library.ini"), QSettings.Format.IniFormat),
    )
    try:
        library.collapseAll()
        library.headings["movement"].setExpanded(True)
        library.filter("BOOST Auto Builder")
        path = "movement/Conveyors/BOOST Auto Builder"
        assert library.headings[path].isExpanded()
        assert not library.headings["movement/Conveyors"].isHidden()
        library.filter("")
        assert library.headings["movement"].isExpanded()
        assert not library.headings[path].isExpanded()
        item = library.rows[reference("pybricks/lessons/conveyor_transfer")]
        library.setCurrentItem(item)
        library.toggle_favorite()
        library.set_view("favorites")
        assert library.topLevelItemCount() == 1
        assert not library.headings
    finally:
        library.close()


def test_existing_value_action_repairs_missing_receiver_in_one_undo(tmp_path, qt_app):
    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.structure import block_menu

    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nleft = Motor(Port.A)\nmotor.run(300)\n"
    )
    session = Session(path)
    view = SourceView(session)
    view.resize(900, 600)
    view.show()
    qt_app.processEvents()
    try:
        slot = next(s for s in view.parameter_slots if s.parameter.name == "motor")
        assert view.parameter_issues[slot.span]
        assert "Motor" in view.parameter_tip(slot)
        menu = block_menu(view, view.parameter_rect(slot).center().toPoint())
        existing = next(
            a.menu() for a in menu.actions() if a.text() == "Select existing value"
        )
        before = session.document.state
        next(a for a in existing.actions() if a.text() == "left").trigger()
        assert session.document.state.source.endswith("left.run(300)\n")
        assert not session.analysis.diagnostics()
        session.editor.undo()
        assert session.document.state is before
        menu.deleteLater()
    finally:
        view.close()
