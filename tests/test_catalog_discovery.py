from little_tinker_rig.core.catalog_history import reference
from little_tinker_rig.core.parameters import choices
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import Parameter, load_module


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
