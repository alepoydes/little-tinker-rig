import pytest

np = pytest.importorskip("numpy")

from little_tinker_rig.core.ldraw import LDraw, rgba  # noqa: E402


@pytest.fixture
def model(tmp_path):
    (tmp_path / "part.dat").write_text(
        "0 Sample part\n3 16 0 0 0 20 0 0 0 -20 0\n2 24 0 0 0 20 0 0\n"
    )
    path = tmp_path / "robot.mpd"
    path.write_text("""0 FILE main.ldr
0 !LITTLE_TINKER_RIG ID left
1 4 10 0 0 1 0 0 0 1 0 0 0 1 part.dat
0 STEP
0 !LITTLE_TINKER_RIG ID right
1 1 -10 0 0 -1 0 0 0 1 0 0 0 1 part.dat
0 STEP
0 !LITTLE_TINKER_RIG ID subassembly
1 14 0 40 0 1 0 0 0 1 0 0 0 1 child.ldr
0 FILE child.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 part.dat
0 STEP
1 16 20 0 0 1 0 0 0 1 0 0 0 1 part.dat
""")
    return path


def test_shared_geometry_transforms_and_nested_steps(model):
    scene = LDraw(model).scene()
    assert len(scene.meshes) == 1
    assert len(scene.instances) == 4
    assert scene.step_count == 4
    assert [i.step for i in scene.instances] == [0, 1, 2, 3]
    assert [i.color for i in scene.instances] == [4, 1, 14, 14]
    assert scene.instances[-1].identity == "subassembly/2"
    np.testing.assert_allclose(scene.bounds(), [[-30, -20, 0], [40, 40, 0]])


@pytest.mark.parametrize("saved, expected", [(2, 2), (99, 3)])
def test_saved_assembly_step_waits_for_model_count(model, qt_app, saved, expected):
    import json

    from little_tinker_rig.qt.assembly import AssemblyPage

    description = model.with_suffix(".json")
    description.write_text(
        json.dumps(
            {
                "format": 1,
                "model": model.name,
                "steps": {"1": {"text": "Start here"}},
            }
        )
    )
    state = {"step": saved}
    page = AssemblyPage(description, state)
    try:
        from little_tinker_rig.i18n import language, set_language

        original_language = language()
        assert page.step == state["step"] == saved
        assert not page.back.isEnabled() and not page.next_step.isEnabled()
        page.loaded(None, "Parts unavailable")
        assert page.error.text()
        assert "Parts unavailable" not in page.error.text()
        try:
            set_language("ru")
            page.retranslate()
            assert "Не удалось загрузить модель робота" in page.error.text()
        finally:
            set_language(original_language)
            page.retranslate()
        assert page.step == state["step"] == saved
        with LDraw(model) as reader:
            page.loaded(reader.scene(), "")
        assert page.step == state["step"] == expected
        assert page.slider.value() == expected
        assert not page.error.text() or "3D" in page.error.text()
    finally:
        page.deleteLater()


def test_circular_references_fail_without_recursion(model):
    (model.parent / "part.dat").write_text("1 16 0 0 0 1 0 0 0 1 0 0 0 1 part.dat")
    with pytest.raises(ValueError, match="Circular"):
        LDraw(model).scene()


def test_flexible_components_keep_geometry_without_exposing_generated_segments(
    tmp_path,
):
    path = tmp_path / "robot.mpd"
    path.write_text("""0 FILE main.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 cable.ldr
0 STEP
1 1 40 0 0 1 0 0 0 1 0 0 0 1 cable.ldr
0 FILE cable.ldr
0 Cable
0 !LDCAD CONTENT [type=path]
1 16 0 0 0 1 0 0 0 1 0 0 0 1 segment.dat
0 STEP
1 16 10 0 0 1 0 0 0 1 0 0 0 1 segment.dat
0 FILE segment.dat
0 Segment
3 16 0 0 0 10 0 0 0 -5 0
""")
    with LDraw(path) as reader:
        scene = reader.scene()
    assert len(scene.instances) == 2
    assert scene.step_count == 2
    assert [i.color for i in scene.instances] == [4, 1]
    assert list(scene.meshes) == ["cable.ldr"]
    assert len(scene.meshes["cable.ldr"].triangles) == 2
    np.testing.assert_allclose(scene.bounds(), [[0, -5, 0], [60, 0, 0]])


def test_inline_geometry_is_not_lost_next_to_parts(model):
    source = model.read_text()
    model.write_text(
        source.replace(
            "0 STEP\n0 !LITTLE_TINKER_RIG ID right",
            "0 STEP\n3 2 0 0 0 0 -100 0 100 0 0\n0 STEP\n0 !LITTLE_TINKER_RIG ID right",
        )
    )
    scene = LDraw(model).scene()
    assert len(scene.instances) == 5
    assert [i.step for i in scene.instances] == [0, 1, 2, 3, 4]
    np.testing.assert_allclose(scene.bounds(), [[-30, -100, 0], [100, 40, 0]])


def test_model_without_steps_hides_assembly_navigation(model, qt_app):
    import json

    from little_tinker_rig.qt.assembly import AssemblyPage

    description = model.parent / "robot.json"
    description.write_text(
        json.dumps({"format": 1, "title": "Sample model", "model": "part.dat"})
    )
    with LDraw(model.parent / "part.dat") as reader:
        scene = reader.scene()
    page = AssemblyPage(description)
    try:
        page.loaded(scene, None)
        assert page.caption.text() == "Sample model"
        assert page.parts_caption.text() == "Parts"
        assert page.parts.count() == 1
        assert all(
            w.isHidden() for w in (page.back, page.next_step, page.slider, page.future)
        )
    finally:
        if page.view:
            page.view.cleanup()
        page.deleteLater()


def test_embedded_colors_and_conditional_edges(tmp_path):
    path = tmp_path / "part.dat"
    path.write_text("""0 Example
0 !COLOUR Lesson_Blue CODE 101 VALUE #123456 EDGE #010203
4 101 0 0 0 20 0 0 20 20 0 0 20 0
5 24 0 0 0 20 0 0 0 20 0 20 20 0
""")
    scene = LDraw(path).scene()
    assert scene.meshes["part.dat"].triangles.shape == (2, 3, 3)
    assert scene.meshes["part.dat"].lines.shape == (1, 4, 3)
    assert rgba(16, scene.colors, 101) == (18 / 255, 52 / 255, 86 / 255, 1)
    assert rgba(24, scene.colors, 101) == (1 / 255, 2 / 255, 3 / 255, 1)


def test_renderer_draws_and_picks_visible_instance(model):
    moderngl = pytest.importorskip("moderngl")
    from little_tinker_rig.qt.lego_view import Camera, Renderer

    try:
        context = moderngl.create_standalone_context(backend="egl")
    except Exception as error:
        pytest.skip(f"No headless OpenGL: {error}")
    try:
        with context:
            scene = LDraw(model).scene()
            camera = Camera(scene.bounds())
            camera.yaw = camera.pitch = 0
            renderer = Renderer(context, scene)
            target = context.simple_framebuffer((128, 128), components=4)
            try:
                renderer.draw(target, camera, 0, picking=True)
                pixels = np.frombuffer(
                    target.read(components=3), dtype=np.uint8
                ).reshape(128, 128, 3)
                assert set(np.unique(pixels[:, :, 0])) == {0, 1}
                y, x = np.argwhere(pixels[:, :, 0] == 1)[0]
                assert renderer.pick((128, 128), int(x), int(y), camera, 0) == 1
                renderer.draw(target, camera, 3, picking=True)
                pixels = np.frombuffer(
                    target.read(components=3), dtype=np.uint8
                ).reshape(128, 128, 3)
                assert set(np.unique(pixels[:, :, 0])) == {0, 1, 2, 3, 4}
            finally:
                target.release()
                renderer.release()
    finally:
        context.release()


def test_qt_views_render_with_independent_native_contexts(model, qt_app):
    pytest.importorskip("moderngl")
    from PySide6.QtCore import QEvent, QObject, QPoint, Qt
    from PySide6.QtGui import QImage, QPlatformSurfaceEvent
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from little_tinker_rig.qt.lego_view import LegoView

    if qt_app.platformName().startswith(("offscreen", "minimal")):
        pytest.skip("Run with QT_QPA_PLATFORM=wayland or xcb to check native Qt GL")

    class SurfaceWatch(QObject):
        destroyed_surface = False

        def eventFilter(self, obj, event):
            if (
                event.type() == QEvent.Type.PlatformSurface
                and event.surfaceEventType()
                == QPlatformSurfaceEvent.SurfaceEventType.SurfaceAboutToBeDestroyed
            ):
                self.destroyed_surface = True
            return False

    scene = LDraw(model).scene()
    views = [LegoView(scene), LegoView(scene)]
    hosts, watches = [], []
    try:
        for view in views:
            host = QWidget()
            layout = QVBoxLayout(host)
            host.resize(360, 280)
            host.show()
            qt_app.processEvents()
            watch = SurfaceWatch(host)
            host.windowHandle().installEventFilter(watch)
            hosts.append(host)
            watches.append(watch)
            view.step = scene.step_count - 1
            layout.addWidget(QWidget.createWindowContainer(view))
        from PySide6.QtTest import QTest

        QTest.qWait(100)
        for view in views:
            assert view.context() is not None and view.context().isValid()
            assert not view.failure
            assert view.renderer is not None
        assert views[0].renderer.ctx is not views[1].renderer.ctx
        # Revisit the first context after initializing the second, then replace
        # Qt's framebuffer by resizing. A valid context must produce real pixels.
        for view, host, watch in zip(views, hosts, watches, strict=True):
            host.resize(440, 340)
            QTest.qWait(100)
            # Capture the freshly drawn back buffer before it is swapped.
            view.makeCurrent()
            view.paintGL()
            frame = view.grabFramebuffer().convertToFormat(QImage.Format.Format_RGB888)
            view.doneCurrent()
            assert not frame.isNull()
            pixels = np.frombuffer(frame.constBits(), dtype=np.uint8).reshape(
                frame.height(), frame.bytesPerLine()
            )[:, : frame.width() * 3]
            assert np.ptp(pixels) > 50
            image = pixels.reshape(frame.height(), frame.width(), 3).astype(int)
            for item in scene.instances:
                center = scene.meshes[item.part].triangles[0].mean(axis=0)
                projected = (
                    view.camera.matrix(frame.width(), frame.height())
                    @ item.transform
                    @ np.array([*center, 1])
                )
                x = int((projected[0] + 1) * frame.width() / 2)
                y = int((1 - projected[1]) * frame.height() / 2)
                assert np.max(np.abs(image[y, x] - [242, 245, 250])) > 20
            scale = view.devicePixelRatio()
            camera_before = view.camera.state()
            QTest.mouseClick(
                view,
                Qt.MouseButton.LeftButton,
                pos=QPoint(round(x / scale), round(y / scale)),
            )
            assert view.selection
            assert view.camera.state() == camera_before
            QTest.mouseClick(
                view,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ControlModifier,
                pos=QPoint(round(x / scale), round(y / scale)),
            )
            assert view.camera.extent == camera_before["extent"]
            assert view.camera.state() != camera_before
            QTest.keyClick(view, Qt.Key.Key_Escape)
            assert not view.selection
            assert not view.failure
            assert not watch.destroyed_surface
            view.cleanup()
            assert view.context().isValid()  # The native context still belongs to Qt.
    finally:
        for view, host in zip(views, hosts, strict=False):
            view.cleanup()
            host.close()
            host.deleteLater()
        qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_selection_preserves_camera_and_explicit_centering_preserves_zoom(
    model, qt_app
):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from little_tinker_rig.qt.lego_view import LegoView

    scene = LDraw(model).scene()
    view = LegoView(scene)
    view.resize(640, 240)
    try:
        view.camera.yaw, view.camera.pitch = -65, 40
        view.step = scene.step_count - 1
        original = view.camera.state()
        view.select([scene.instances[i].identity for i in (0, 2)])
        assert view.camera.state() == original
        view.select([scene.instances[i].identity for i in (0, 2)], center=True)
        assert view.camera.extent == original["extent"]
        assert (view.camera.yaw, view.camera.pitch) == (-65, 40)
        points = scene.corners([scene.instances[i] for i in (0, 2)]).reshape(-1, 3)
        projected = (points - view.camera.center) @ np.array(view.camera.basis()).T
        np.testing.assert_allclose(projected.min(0) + projected.max(0), 0, atol=1e-12)
        point = np.array([*view.camera.center, 1])
        extent = view.camera.extent
        for kind, position, button, buttons in (
            (
                QEvent.Type.MouseButtonPress,
                (100, 100),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
            ),
            (
                QEvent.Type.MouseMove,
                (160, 130),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
            ),
            (
                QEvent.Type.MouseButtonRelease,
                (160, 130),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
            ),
            (
                QEvent.Type.MouseMove,
                (200, 150),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
            ),
        ):
            event = QMouseEvent(
                kind,
                QPointF(*position),
                QPointF(*position),
                button,
                buttons,
                Qt.KeyboardModifier.ShiftModifier,
            )
            qt_app.sendEvent(view, event)
        assert view.camera.extent == extent
        assert (view.camera.yaw, view.camera.pitch) == (-65, 40)
        np.testing.assert_allclose(
            (view.camera.matrix(640, 240) @ point)[:2], [120 / 640, -60 / 240]
        )
        before = view.camera.state()
        view.select(())
        assert view.camera.state() == before
    finally:
        view.deleteLater()
        qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_zoom_interest_follows_selection_step_and_isolated_group(model, qt_app):
    from PySide6.QtCore import QEvent

    from little_tinker_rig.qt.lego_view import LegoView

    scene = LDraw(model).scene()
    view = LegoView(scene)
    try:

        def check(indices):
            expected = scene.corners([scene.instances[i] for i in indices])
            np.testing.assert_array_equal(
                view.interest_points(), expected.reshape(-1, 3)
            )

        view.future = True
        view.select([scene.instances[3].identity])
        check([0])  # A future selection cannot redirect navigation.
        view.step = 2
        check([0, 1, 2])
        view.select([scene.instances[i].identity for i in (0, 2)])
        check([0, 2])
        view.group = (3, 4)
        check([2])
        view.select(())
        check([2])
        view.step = 3
        check([2, 3])
    finally:
        view.deleteLater()
        qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_selected_copies_are_visible_through_geometry_but_not_future_parts(tmp_path):
    moderngl = pytest.importorskip("moderngl")
    from little_tinker_rig.qt.lego_view import Camera, Renderer

    try:
        context = moderngl.create_standalone_context(backend="egl")
    except Exception as error:
        pytest.skip(f"No headless OpenGL: {error}")
    (tmp_path / "part.dat").write_text(
        "4 16 -8 -8 0 8 -8 0 8 8 0 -8 8 0\n" "2 24 -8 -8 0 8 -8 0\n"
    )
    (tmp_path / "cover.dat").write_text("4 16 -50 -30 0 50 -30 0 50 30 0 -50 30 0\n")
    path = tmp_path / "robot.ldr"
    path.write_text(
        "1 4 -25 0 0 1 0 0 0 1 0 0 0 1 part.dat\n"
        "1 4 25 0 0 1 0 0 0 1 0 0 0 1 part.dat\n"
        "1 1 0 0 10 1 0 0 0 1 0 0 0 1 cover.dat\n"
        "0 STEP\n1 4 0 0 20 1 0 0 0 1 0 0 0 1 part.dat\n"
    )
    with LDraw(path) as reader:
        scene = reader.scene()
    camera = Camera(scene.bounds())
    camera.yaw = camera.pitch = 0
    try:
        with context:
            renderer = Renderer(context, scene)
            target = context.simple_framebuffer((128, 128), components=4)

            def draw(**options):
                renderer.draw(target, camera, 0, **options)
                return np.frombuffer(target.read(components=3), dtype=np.uint8).reshape(
                    128, 128, 3
                )

            try:
                original = draw()
                highlighted = draw(selected=(1, 2, 4))
                # Qt composites the result; overlays must keep opaque alpha.
                rgba_pixels = np.frombuffer(
                    target.read(components=4), dtype=np.uint8
                ).reshape(-1, 4)
                assert np.all(rgba_pixels[:, 3] == 255)
                for point in ((-25, 0, 0, 1), (25, 0, 0, 1)):
                    x, y = ((camera.matrix(128, 128) @ point)[:2] + 1) * 64
                    x, y = int(x), int(y)
                    assert (
                        np.max(np.abs(highlighted[y, x].astype(int) - original[y, x]))
                        > 20
                    )
                    assert renderer.pick((128, 128), x, y, camera, 0) == 3
                # Future geometry stays hidden, even when requested in a selection.
                np.testing.assert_array_equal(highlighted[64, 64], original[64, 64])
                np.testing.assert_array_equal(draw(), original)
                np.testing.assert_array_equal(
                    draw(selected=(1, 2), group=(3, 3)), draw(group=(3, 3))
                )
            finally:
                renderer.release()
                target.release()
    finally:
        context.release()


def test_assembly_inspection_preserves_step_and_selects_all_copies(model, qt_app):
    import json

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtTest import QTest

    from little_tinker_rig.qt.assembly import AssemblyPage

    model.write_text(
        model.read_text().replace(
            "0 STEP\n0 !LITTLE_TINKER_RIG ID right",
            "0 !LITTLE_TINKER_RIG ID copy\n1 4 40 0 0 1 0 0 0 1 0 0 0 1 part.dat\n0 STEP\n0 !LITTLE_TINKER_RIG ID right",
        )
    )
    path = model.parent / "robot.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "model": model.name,
                "devices": [
                    {"instance": "left", "name": "Motor", "port": "A", "type": "motor"},
                    {
                        "instance": "right",
                        "name": "Sensor",
                        "port": "B",
                        "type": "color",
                    },
                ],
            }
        )
    )
    page = AssemblyPage(path)
    page.attempted = True
    with LDraw(model) as reader:
        page.loaded(reader.scene(), None)
    page.show()
    page.activateWindow()
    assert QTest.qWaitForWindowActive(page)
    qt_app.processEvents()
    try:
        assert page.devices.count() == 2
        assert page.devices.findData("right") == -1
        assert page.group_controls.isHidden()
        point = page.parts.visualItemRect(page.parts.item(0)).center()
        QTest.mouseClick(page.parts.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert {i.identity for i in page.selected_items} == {"left", "copy"}
        QTest.mouseClick(page.parts.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert not page.selected_items
        QTest.mouseClick(page.parts.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.keyClick(page.parts, Qt.Key.Key_Escape)
        assert not page.selected_items
        page.devices.setCurrentIndex(1)
        assert [i.identity for i in page.selected_items] == ["left"]
        assert page.step == 0
        page.set_step(2)
        assert not page.selected_items
        assert page.devices.findData("right") > 0
        page.groups.setCurrentIndex(page.groups.findData("subassembly"))
        assert page.step == 2  # This subassembly also has a future step 3.
        page.set_step(3)
        assert page.future.isHidden()
        page.set_step(0)
        assert page.groups.currentData() is None
        assert page.devices.findData("right") == -1
    finally:
        if page.view:
            page.view.cleanup()
        page.close()
        page.deleteLater()
        qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_pilot_mating_points_track_and_ground_plane():
    import os
    from pathlib import Path

    from little_tinker_rig.core.lessons import lessons_directory

    archive = os.environ.get("LITTLE_TINKER_RIG_TEST_LDRAW")
    if not archive:
        pytest.skip(
            "Set LITTLE_TINKER_RIG_TEST_LDRAW to a downloaded official ZIP for the model integration check"
        )
    root = lessons_directory() / "first_drive" / "robot"
    with LDraw(root / "car.mpd", Path(archive)) as reader:
        scene = reader.scene()
    instances = {i.identity: i for i in scene.instances}
    assert scene.step_count == 11
    assert len(instances) == 20
    assert all(len(scene.meshes[i.part].triangles) for i in scene.instances)

    def point(name, local):
        item = instances[name]
        return (item.transform @ [*local, 1])[:3]

    for side, x in (("left", -70), ("right", 70)):
        # Mounting hole axes meet the lowest side holes of the hub.
        for local_z, world_z in ((-20, 80), (140, -80)):
            np.testing.assert_allclose(
                point(side + "-motor", [0, 30, local_z]), [x, -10, world_z]
            )
        wheel = scene.bounds([instances[side + "-wheel"]])
        assert wheel[1, 1] == pytest.approx(60)
    assert (
        abs(point("right-wheel", [0, 0, 0])[0] - point("left-wheel", [0, 0, 0])[0])
        * 0.4
        == 136
    )
    assert scene.bounds([instances["rear-support"]])[1, 1] == pytest.approx(60)
    for x in (-60, 60):
        np.testing.assert_allclose(
            point("sensor-beam", [0, 10, x]), point("distance-sensor", [-x, 0, 10])
        )
