import ast

import pytest

from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import builtin_snippets, load_module
from little_tinker_rig.core.variants import variant_bindings, variant_source


def selected(source, snippets):
    session = Session.fragment(source, snippets)
    session.editor.selection = session.document.syntax.tree.body[-1]
    return session, session.selected_match()


def test_optional_variant_preserves_fixed_behavior_names_and_one_undo():
    snippets = builtin_snippets()
    session, match = selected("wheel.run_target(600, 90, wait=False)", snippets)
    target = next(
        s
        for s in snippets
        if s.identity.endswith("/motor_run_target_speed_target_angle_wait_then")
    )
    values = variant_bindings(session, match, target)
    assert values["motor"] == "wheel"
    assert values["wait"] == "False"
    before = session.document.state
    values["target_angle"] = "120"
    preview = variant_source(session, match, target, values)
    assert session.document.state is before and not session.document.can_undo
    session.change_variant(target, values)
    assert session.document.state.source == preview
    call = session.document.syntax.tree.body[0].value
    assert ast.unparse(call) == "wheel.run_target(600, 120, wait=False, then=Stop.HOLD)"
    session.editor.undo()
    assert session.document.state is before and not session.document.can_undo
    session.editor.redo()
    assert session.document.state.source == preview


@pytest.mark.parametrize("method", ["run_target", "move_to"])
def test_variant_reorders_keyword_templates_without_reordering_evaluation(method):
    snippets = load_module(
        """
@inline_block(variant="Old order")
def old(motor=motor, angle=90, speed=300, wait=True, then=Stop.HOLD):
    motor.run_target(target_angle=angle, speed=speed, then=then, wait=wait)

@inline_block(family="test/motor/old", variant="Options", bindings={"target": "angle"})
def options(motor=motor, speed=300, target=90, wait=True, then=Stop.HOLD, extra=1):
    motor.run_target(speed, target, wait=wait, then=then, extra=extra)
""".replace("motor.run_target(speed, target,", f"motor.{method}(speed, target,"),
        "test/motor",
        "1",
    )
    session, match = selected(
        "motor.run_target(target_angle=next_value(), speed=next_value(), then=stop(), wait=waiting())",
        snippets,
    )
    if method == "move_to":
        before = session.document.state
        with pytest.raises(ValueError, match="evaluation order"):
            variant_source(
                session,
                match,
                snippets[1],
                variant_bindings(session, match, snippets[1]),
            )
        assert session.document.state is before and not session.document.can_undo
        return
    preview = variant_source(
        session, match, snippets[1], variant_bindings(session, match, snippets[1])
    )
    calls = []

    class Motor:
        def run_target(self, **kwargs):
            calls.append(kwargs)

    def value():
        calls.append("value")
        return len(calls)

    exec(
        preview,
        {
            "motor": Motor(),
            "next_value": value,
            "stop": lambda: calls.append("stop") or "hold",
            "waiting": lambda: calls.append("wait") or False,
        },
    )
    assert calls == [
        "value",
        "value",
        "stop",
        "wait",
        {
            "target_angle": 1,
            "speed": 2,
            "then": "hold",
            "wait": False,
            "extra": 1,
        },
    ]


def test_variant_keeps_declaration_comments_and_string_contents():
    snippets = load_module(
        """
@inline_block(names=("device",), variant="Default")
def create(port="A"):
    device = Device(port)

@inline_block(names=("device",), family="test/devices/create", variant="Directed")
def directed(port="A", direction=1):
    device = Device(port, direction=direction)
""",
        "test/devices",
        "1",
    )
    session, match = selected(
        """# Keep the left wheel.
left = Device(
    # Port label stays with the edit.
    "line one\\n  line two"
)
""",
        snippets,
    )
    values = variant_bindings(session, match, snippets[1])
    source = variant_source(session, match, snippets[1], values)
    assert source.count("# Keep the left wheel.") == 1
    assert source.count("# Port label stays with the edit.") == 1
    assert ast.parse(source).body[0].targets[0].id == "left"
    created = []
    exec(source, {"Device": lambda port, **kwargs: created.append((port, kwargs))})
    assert created == [("line one\n  line two", {"direction": 1})]


def test_variant_result_must_fit_the_existing_parent_input():
    snippets = load_module(
        """
@inline_block(variant="Boolean")
def boolean(value=1) -> "bool":
    return bool(value)

@inline_block(family="test/values/boolean", variant="String")
def string(value=1) -> "str":
    return str(value)
""",
        "test/values",
        "1",
    )
    session = Session.fragment('enabled: "bool" = bool(1)\n', snippets)
    session.editor.selection = session.document.syntax.tree.body[0].value
    match = session.selected_match()
    before = session.document.state
    with pytest.raises(ValueError, match="does not fit"):
        session.change_variant(
            snippets[1], variant_bindings(session, match, snippets[1])
        )
    assert session.document.state is before and not session.document.can_undo


def test_operator_variant_preserves_grouping_and_control_variant_removes_optional_value():
    snippets = builtin_snippets()
    by_id = {s.identity: s for s in snippets}
    session, match = selected("(2 + 3) + 4", (by_id["python/basics/sum_values"],))
    target = by_id["python/basics/product"]
    source = variant_source(
        session, match, target, variant_bindings(session, match, target)
    )
    assert eval(source) == 20
    session, match = selected("yield 1", (by_id["python/objects/yield_value"],))
    target = by_id["python/objects/yield_control"]
    source = variant_source(
        session, match, target, variant_bindings(session, match, target)
    )
    assert isinstance(ast.parse(source).body[0].value, ast.Yield)
    assert ast.parse(source).body[0].value.value is None


def test_variant_dialog_preserves_filtered_values_and_applies_one_edit(qt_app):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.variants import VariantDialog

    session, _ = selected("motor.run_target(300, 90, wait=False)", builtin_snippets())
    view = SourceView(session)
    view.expression_level = "beginner"
    dialog = VariantDialog(view)
    before = session.document.state
    try:
        assert dialog.variant.count() == 1
        assert "wait=False" in session.document.state.source
        dialog.reject()
        assert session.document.state is before and not session.document.can_undo
        view.expression_level = "all"
        changes = []
        view.changed.connect(lambda: changes.append(session.document.state))

        def edit():
            current = QApplication.activeModalWidget()
            assert isinstance(current, VariantDialog)
            current.variant.setCurrentIndex(
                current.variant.findData(
                    "pybricks/motor_motion/motor_run_target_speed_target_angle_wait_then"
                )
            )
            assert current.fields["wait"].currentText() == "False"
            assert current.more.isChecked()
            current.more.setChecked(False)
            assert "wait = False" in current.summary.text()
            current.fields["target_angle"].setCurrentText("broken(")
            assert not current.update_preview()
            assert not current.buttons.button(
                QDialogButtonBox.StandardButton.Ok
            ).isEnabled()
            current.fields["target_angle"].setCurrentText("180")
            assert current.update_preview()
            assert "180" in current.preview.toPlainText()
            assert session.document.state is before
            QTest.mouseClick(
                current.buttons.button(QDialogButtonBox.StandardButton.Ok),
                Qt.MouseButton.LeftButton,
            )

        QTimer.singleShot(0, edit)
        view.edit_parameters()
        assert len(changes) == 1
        assert (
            "180" in session.document.state.source
            and "wait=False" in session.document.state.source
        )
        session.editor.undo()
        assert session.document.state is before and not session.document.can_undo
    finally:
        dialog.deleteLater()
        view.close()


def test_variant_dialog_rejects_stale_source(qt_app):
    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.variants import VariantDialog

    session, _ = selected("motor.run_target(300, 90)", builtin_snippets())
    view = SourceView(session)
    dialog = VariantDialog(view)
    try:
        session.editor.commit("motor.stop()")
        changed = session.document.state
        dialog.apply()
        assert dialog.error.text() and session.document.state is changed
    finally:
        dialog.deleteLater()
        view.close()


def test_catalog_properties_edit_source_once_and_validate_shared_fields(
    tmp_path, qt_app
):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.catalog_properties import CatalogProperties

    window = Studio(tmp_path / "program.py")
    window.confirm_close = lambda *_: True
    try:
        editor = window.block_editor
        editor.create("""@inline_block(level="intermediate")
def show(value=1, end="\\n"):
    print(value, end=end)
""")
        original = editor.code.toPlainText()

        def properties():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, CatalogProperties)
            dialog.category.setCurrentIndex(dialog.category.findData("output"))
            dialog.fields["value"][0].setText("end")
            dialog.apply()
            assert dialog.error.text()
            assert editor.code.toPlainText() == original
            dialog.fields["value"][0].setText("message")
            dialog.fields["end"][1].setChecked(True)
            dialog.variant.setText("Print text")
            dialog.apply()

        QTimer.singleShot(0, properties)
        editor.edit_catalog()
        snippet = editor.preview_snippet
        assert snippet.category == "output" and snippet.variant == "Print text"
        assert snippet.bindings == {"value": "message"}
        assert snippet.advanced == ("end",)
        editor.code.undo()
        assert editor.code.toPlainText() == original
    finally:
        window.close()


def test_context_variant_is_immediate_undoable_filtered_and_rejects_stale_menu(qt_app):
    from little_tinker_rig.qt.editor import SourceView
    from little_tinker_rig.qt.structure import block_menu

    session, _ = selected("wheel.brake()", builtin_snippets())
    view = SourceView(session)
    view.resize(700, 500)
    view.show()
    qt_app.processEvents()
    errors, changes = [], []
    view.failed.connect(errors.append)
    view.changed.connect(lambda: changes.append(session.document.state))
    menus = []
    try:
        point = view._rect(1, 2).center().toPoint()
        before = session.document.state
        menu = block_menu(view, point)
        menus.append(menu)
        variants = next(a.menu() for a in menu.actions() if a.text() == "Variant")
        action = next(a for a in variants.actions() if a.text() == "Coast")
        action.trigger()
        assert not errors and len(changes) == 1
        assert session.document.state.source == "wheel.stop()\n"
        session.editor.undo()
        assert session.document.state is before and not session.document.can_undo
        view.refresh_source()
        view.expression_ids = frozenset({"pybricks/motors/stop_motor"})
        restricted = block_menu(view, point)
        menus.append(restricted)
        assert not any(a.text() == "Variant" for a in restricted.actions())
        session.editor.commit("wheel.hold()")
        changed = session.document.state
        action.trigger()
        assert errors and session.document.state is changed and len(changes) == 1
    finally:
        for menu in menus:
            menu.deleteLater()
        view.close()
