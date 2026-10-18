"""Start-workspace navigation and persistent learning attempts."""

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton

from little_tinker_rig.core.lessons import StudentProject
from little_tinker_rig.examples import examples_directory
from little_tinker_rig.i18n import language, set_language
from little_tinker_rig.qt.app import Studio


def close(window):
    window.recovery.close()
    window.deleteLater()


def rendered_images(browser):
    document = browser.document()
    pictures = []
    block = document.begin()
    while block.isValid():
        fragment = block.begin()
        while not fragment.atEnd():
            item = fragment.fragment()
            if item.charFormat().isImageFormat():
                name = item.charFormat().toImageFormat().name()
                if not name.startswith("lesson-number:"):
                    pictures.append(
                        document.resource(
                            QTextDocument.ResourceType.ImageResource, QUrl(name)
                        )
                    )
            fragment += 1
        block = block.next()
    return pictures


def recent_labels(window):
    return [
        [
            label.text()
            for label in window.home_page.recent_layout.itemAt(index)
            .widget()
            .findChildren(QLabel)
        ]
        for index in range(window.home_page.recent_layout.count())
    ]


def test_start_page_reuses_empty_document_and_creates_no_recovery(tmp_path, qt_app):
    window = Studio()
    try:
        assert window.pages.currentWidget() is window.home_page
        assert window._unused_startup_placeholder()
        assert window.documents.count() == 1
        assert window.recovery.flush()
        assert not window.recovery.path.exists()
        window.new_file()
        assert window.pages.currentIndex() == 0
        assert window.documents.count() == 1
        assert window.startup_placeholder is None
        window.set_mode(5)
        assert window.home_page.recent_layout.count() == 1
        recent = window.home_page.recent_layout.itemAt(0).widget()
        assert any(
            label.text() == "Untitled program" for label in recent.findChildren(QLabel)
        )
        window.set_mode(0)
        window.session.editor.commit("value = 1\n")
        window.refresh_views()
        window.set_mode(5)
        assert window.windowTitle().startswith("● Home")
    finally:
        close(window)


def test_home_first_project_resumes_one_attempt(tmp_path, qt_app):
    original = language()
    window = Studio()
    window.show()
    try:
        card = window.home_page.project_layout.itemAt(0).widget()
        button = card.findChild(QPushButton, "homeCardAction")
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.pages.currentIndex() == 2
        assert window.documents.count() == 1
        project = window.document_page.lesson_project
        assert project.lesson.data["id"] == "first-python-program"
        assert project.main.read_text(encoding="utf-8").startswith('"""First program')
        assert window.help_page.current == "lesson/instructions"
        pictures = rendered_images(window.help_page.browser)
        assert len(pictures) == 1 and pictures[0].width() > 0
        panel_images = rendered_images(window.lessons.cards["message"]["body"])
        assert len(panel_images) == 1 and panel_images[0].width() > 0
        set_language("ru")
        window.retranslate()
        assert "Придумай своё сообщение" in window.help_page.browser.toPlainText()
        assert len(rendered_images(window.lessons.cards["message"]["body"])) == 1
        window.lessons.cards["message"]["check"].setChecked(True)
        window.set_mode(5)
        assert window.home_page.recent_layout.count() == 1
        recent = window.home_page.recent_layout.itemAt(0).widget()
        assert any("1/3" in label.text() for label in recent.findChildren(QLabel))
        button = (
            window.home_page.project_layout.itemAt(0)
            .widget()
            .findChild(QPushButton, "homeCardAction")
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.document_page.lesson_project.root == project.root
        assert window.document_page.lesson_project.score == (1, 3)
        assert len(StudentProject.attempts(Path("lessons/first_python"))) == 1
    finally:
        set_language(original)
        close(window)


def test_saved_lesson_is_one_recent_attempt_after_restart(
    tmp_path, qt_app, monkeypatch
):
    archive = tmp_path / "first.ltr"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(archive), "LittleTinker Rig (*.ltr)"),
    )
    first = Studio()
    second = None
    try:
        first.lessons.open(Path("lessons/first_python"))
        attempt = first.document_page.lesson_project
        assert first.lessons.save(attempt, choose=True)
        first.session.editor.commit('print("after the save")\n')
        assert first.recovery.flush()
        first.set_mode(5)
        assert len(recent_labels(first)) == 1
        assert recent_labels(first)[0][0] == "First Python program"
        root = attempt.root
        close(first)

        second = Studio()
        assert len(recent_labels(second)) == 1
        resumed = StudentProject.latest(Path("lessons/first_python"))
        assert resumed.root == root
        assert resumed.path == archive
        assert resumed.dirty
        second.open_recent(archive)
        assert second.document_page.lesson_project.root == root
        second.set_mode(5)
        button = (
            second.home_page.recent_layout.itemAt(0)
            .widget()
            .findChild(QPushButton, "homeCardAction")
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert second.document_page.lesson_project.root == root
        assert second.document_page.text == 'print("after the save")\n'
        assert second.lessons.save(second.document_page.lesson_project)
        assert StudentProject.open(archive).main.read_text(encoding="utf-8") == (
            'print("after the save")\n'
        )
        assert len(StudentProject.attempts(Path("lessons/first_python"))) == 1
    finally:
        if second is not None:
            close(second)
        elif not first.recovery.closed:
            close(first)


def test_legacy_saved_lesson_archive_is_not_a_second_recent_item(tmp_path, qt_app):
    attempt = StudentProject.create(Path("lessons/first_python"))
    archive = tmp_path / "old.ltr"
    attempt.save(archive)
    manifest = attempt.root / "project.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["archive"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    window = Studio()
    try:
        window.remember_file(archive)
        window.set_mode(5)
        assert len(recent_labels(window)) == 1
        assert recent_labels(window)[0][0] == "First Python program"
    finally:
        close(window)


def test_standalone_lesson_archive_is_labeled_as_a_project(tmp_path, qt_app):
    attempt = StudentProject.create(Path("lessons/first_python"))
    archive = tmp_path / "standalone.ltr"
    attempt.save(archive)
    attempt.discard_working_copy()
    window = Studio()
    try:
        window.remember_file(archive)
        window.set_mode(5)
        assert recent_labels(window) == [["standalone.ltr", "Lesson project"]]
    finally:
        close(window)


def test_home_numbers_multiple_attempts_in_both_languages(tmp_path, qt_app):
    original = language()
    window = Studio()
    try:
        first = window.lessons.open(Path("lessons/first_python")).lesson_project
        second = window.lessons.open(
            Path("lessons/first_python"), new=True
        ).lesson_project
        window.set_mode(5)
        labels = recent_labels(window)
        assert len(labels) == 2
        assert "attempt 2" in labels[0][1]
        assert "attempt 1" in labels[1][1]
        set_language("ru")
        window.retranslate()
        labels = recent_labels(window)
        assert "попытка 2" in labels[0][1]
        assert "попытка 1" in labels[1][1]
        button = (
            window.home_page.recent_layout.itemAt(1)
            .widget()
            .findChild(QPushButton, "homeCardAction")
        )
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert window.document_page.lesson_project.root == first.root
        assert window.document_page.lesson_project.root != second.root
    finally:
        set_language(original)
        close(window)


def test_explicit_file_skips_home_and_does_not_add_placeholder(tmp_path, qt_app):
    path = tmp_path / "my_program.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    window = Studio(path)
    try:
        assert window.pages.currentIndex() == 0
        assert window.documents.count() == 1
        assert window.startup_placeholder is None
        assert window.document_page.session.project.path == path
    finally:
        close(window)


def test_home_filter_and_russian_caption(tmp_path, qt_app):
    original = language()
    window = Studio()
    try:
        set_language("ru")
        window.retranslate()
        assert window.home_button.toolTip() == "Начало"
        assert window.home_page.heading.text() == "Создай что-нибудь сегодня"
        window.home_page.kit.setCurrentIndex(window.home_page.kit.findData("none"))
        assert window.home_page.project_layout.count() == 1
        assert window.settings.value("homeKit") == "none"
        another = Studio()
        try:
            assert another.home_page.kit.currentData() == "none"
            assert another.home_page.project_layout.count() == 1
        finally:
            close(another)
    finally:
        set_language(original)
        close(window)


def test_example_attempt_is_one_recent_item(tmp_path, qt_app):
    window = Studio()
    try:
        window.open_document(examples_directory() / "first.py")
        assert window.documents.count() == 1
        window.set_mode(5)
        assert window.home_page.recent_layout.count() == 1
        recent = window.home_page.recent_layout.itemAt(0).widget()
        assert any(
            label.text() == "Example attempt" for label in recent.findChildren(QLabel)
        )
    finally:
        close(window)


def test_recovery_from_home_shows_restored_program(tmp_path, qt_app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    path = tmp_path / "recovered.py"
    path.write_text("answer = 1\n", encoding="utf-8")
    old = Studio(path)
    restored = None
    try:
        old.session.editor.commit("answer = 2\n")
        assert old.recovery.flush()
        old.recovery.lock.unlock()
        old.recovery.lock = None
        old.recovery.closed = True
        monkeypatch.setattr(
            QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
        )
        restored = Studio()
        assert restored.pages.currentIndex() == 5
        restored.recovery.offer()
        assert restored.pages.currentIndex() == 0
        assert restored.documents.count() == 1
        assert restored.document_page.text == "answer = 2\n"
        assert restored.startup_placeholder is None
    finally:
        close(old)
        if restored is not None:
            close(restored)


def test_home_temporarily_hides_lesson_tasks_without_losing_progress(tmp_path, qt_app):
    window = Studio()
    window.resize(1380, 880)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        qt_app.processEvents()
        project = window.document_page.lesson_project
        assert window.lessons.panel.isVisible()
        window.set_mode(5)
        qt_app.processEvents()
        assert not window.lessons.panel.isVisible()
        assert not window.lessons.progress_button.isVisible()
        assert project.progress["panel_expanded"]
        window.set_mode(0)
        qt_app.processEvents()
        assert window.lessons.panel.isVisible()
        assert window.document_page.lesson_project is project
    finally:
        close(window)


def test_rejected_home_navigation_keeps_editor_selected(tmp_path, qt_app, monkeypatch):
    window = Studio(tmp_path / "work.py")
    try:
        monkeypatch.setattr(window, "finish_parameters", lambda: False)
        window.home_button.click()
        assert window.pages.currentIndex() == 0
        assert window.modes.currentRow() == 0
        assert not window.home_button.isChecked()
    finally:
        close(window)


def test_clearing_recent_files_refreshes_home(tmp_path, qt_app):
    path = tmp_path / "saved.py"
    path.write_text("print(1)\n", encoding="utf-8")
    window = Studio(path)
    try:
        window.set_mode(5)
        assert window.home_page.recent_layout.count() == 1
        window.clear_recent_files()
        assert window.home_page.recent_layout.count() == 0
        assert window.home_page.recent_title.isHidden()
        assert window.settings.value("recentActivity") is None
    finally:
        close(window)


def test_first_python_task_illustrations_render_in_both_languages(tmp_path, qt_app):
    original = language()
    window = Studio(tmp_path / "plain.py")
    window.resize(1380, 880)
    window.show()
    try:
        window.lessons.open(Path("lessons/first_python"))
        for code in ("en", "ru"):
            set_language(code)
            window.retranslate()
            for index, stage in enumerate(window.lessons.current.lesson.stages):
                window.lessons.select_stage(index)
                qt_app.processEvents()
                pictures = rendered_images(window.lessons.cards[stage["id"]]["body"])
                assert len(pictures) == 1 and pictures[0].width() > 0
    finally:
        set_language(original)
        close(window)
