import pytest

np = pytest.importorskip("numpy")

from pyblocks.core.ldraw import LDraw, rgba  # noqa: E402


@pytest.fixture
def model(tmp_path):
    (tmp_path / "part.dat").write_text(
        "0 Sample part\n3 16 0 0 0 20 0 0 0 -20 0\n2 24 0 0 0 20 0 0\n"
    )
    path = tmp_path / "robot.mpd"
    path.write_text("""0 FILE main.ldr
0 !PYBLOCKS ID left
1 4 10 0 0 1 0 0 0 1 0 0 0 1 part.dat
0 STEP
0 !PYBLOCKS ID right
1 1 -10 0 0 -1 0 0 0 1 0 0 0 1 part.dat
0 STEP
0 !PYBLOCKS ID subassembly
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


def test_circular_references_fail_without_recursion(model):
    (model.parent / "part.dat").write_text("1 16 0 0 0 1 0 0 0 1 0 0 0 1 part.dat")
    with pytest.raises(ValueError, match="Circular"):
        LDraw(model).scene()


def test_inline_geometry_is_not_lost_next_to_parts(model):
    source = model.read_text()
    model.write_text(
        source.replace(
            "0 STEP\n0 !PYBLOCKS ID right",
            "0 STEP\n3 2 0 0 0 0 -100 0 100 0 0\n0 STEP\n0 !PYBLOCKS ID right",
        )
    )
    scene = LDraw(model).scene()
    assert len(scene.instances) == 5
    assert [i.step for i in scene.instances] == [0, 1, 2, 3, 4]
    np.testing.assert_allclose(scene.bounds(), [[-30, -100, 0], [100, 40, 0]])


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
    from pyblocks.qt.lego_view import Camera, Renderer

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
    from PySide6.QtGui import QImage

    from pyblocks.qt.lego_view import LegoView

    if qt_app.platformName().startswith(("offscreen", "minimal")):
        pytest.skip("Run with QT_QPA_PLATFORM=wayland or xcb to check native Qt GL")
    scene = LDraw(model).scene()
    views = [LegoView(scene), LegoView(scene)]
    try:
        for view in views:
            view.resize(320, 240)
            view.step = scene.step_count - 1
            view.show()
        qt_app.processEvents()
        for view in views:
            assert view.context() is not None and view.context().isValid()
            assert not view.failure
            assert view.renderer is not None
        assert views[0].renderer.ctx is not views[1].renderer.ctx
        # Revisit the first context after initializing the second, then replace
        # Qt's framebuffer by resizing. A valid context must produce real pixels.
        for view in views:
            view.resize(384, 256)
            qt_app.processEvents()
            frame = view.grabFramebuffer().convertToFormat(QImage.Format.Format_RGB888)
            assert not frame.isNull()
            pixels = np.frombuffer(frame.constBits(), dtype=np.uint8).reshape(
                frame.height(), frame.bytesPerLine()
            )[:, : frame.width() * 3]
            assert np.ptp(pixels) > 50
            assert not view.failure
            view.cleanup()
            assert view.context().isValid()  # The native context still belongs to Qt.
    finally:
        for view in views:
            view.cleanup()
            view.close()
            view.deleteLater()
        qt_app.processEvents()


def test_pilot_mating_points_track_and_ground_plane():
    import os
    from pathlib import Path

    from pyblocks.core.lessons import lessons_directory

    archive = os.environ.get("PYBLOCKS_TEST_LDRAW")
    if not archive:
        pytest.skip(
            "Set PYBLOCKS_TEST_LDRAW to a downloaded official ZIP for the model integration check"
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
