import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("moderngl")
pytest.importorskip("PySide6")

from pyblocks.core.ldraw import box_corners  # noqa: E402
from pyblocks.qt.lego_view import Camera  # noqa: E402


def camera_and_points(screen_bounds):
    camera = Camera(np.array([[-1000.0] * 3, [1000.0] * 3]))
    camera.extent = 100.0
    # Exercise a rotated camera, not just the world XY plane.
    points = box_corners(np.array(screen_bounds)) @ np.array(camera.basis())
    return camera, points


def projected_bounds(camera, points, aspect):
    positions = np.column_stack([points, np.ones(len(points))])
    projected = positions @ camera.matrix(aspect * 100, 100).T
    return np.array([projected.min(0), projected.max(0)])[:, :2]


@pytest.mark.parametrize("aspect", [0.5, 1.0, 2.5])
@pytest.mark.parametrize("direction", [-1, 1])
def test_zoom_holds_outer_edges_until_selection_is_centered(aspect, direction):
    camera, points = camera_and_points([[60 * aspect, 60, -20], [80 * aspect, 80, 20]])
    points *= direction
    original = camera.state()
    camera.zoom(1.05, points, aspect)
    np.testing.assert_allclose(camera.center, original["center"], atol=1e-12)
    # Cross the inset boundary. Both outer edges settle at 90% of the viewport.
    camera.zoom(1.25 / 1.05, points, aspect)
    bounds = projected_bounds(camera, points, aspect) * direction
    np.testing.assert_allclose(bounds.max(0), 0.9, atol=1e-12)
    previous = abs(bounds.mean(0))
    for _ in range(30):
        camera.zoom(1.1, points, aspect)
        bounds = projected_bounds(camera, points, aspect) * direction
        middle = abs(bounds.mean(0))
        assert np.all(middle <= previous + 1e-12)
        if np.any(middle > 1e-12):
            np.testing.assert_allclose(bounds.max(0), 0.9, atol=1e-12)
        previous = middle
    np.testing.assert_allclose(middle, 0, atol=1e-12)
    assert (camera.yaw, camera.pitch) == (original["yaw"], original["pitch"])
    # Zooming out never reverses the corrective pan.
    centered = camera.center.copy()
    camera.zoom(0.1, points, aspect)
    np.testing.assert_array_equal(camera.center, centered)


@pytest.mark.parametrize(
    "bounds",
    [
        [[240, -20, 0], [260, 20, 10]],  # Already outside after a manual pan.
        [[-200, -200, 0], [260, 240, 10]],  # Larger than the window.
    ],
)
def test_zoom_recovers_gradually_even_when_target_is_already_outside(bounds):
    camera, points = camera_and_points(bounds)
    before = projected_bounds(camera, points, 1)
    camera.zoom(100 / 99, points)
    after = projected_bounds(camera, points, 1)
    endangered = before[1] > 0.9
    np.testing.assert_allclose(after[1, endangered], before[1, endangered], atol=1e-12)
    assert np.linalg.norm(camera.center) < 4


def test_zoom_is_independent_of_wheel_event_subdivision_and_respects_scale_limits():
    camera, points = camera_and_points([[60, 10, -20], [80, 30, 20]])
    other, _ = camera_and_points([[60, 10, -20], [80, 30, 20]])
    camera.zoom(20, points)
    for _ in range(100):
        other.zoom(20 ** (1 / 100), points)
    np.testing.assert_allclose(other.center, camera.center, atol=1e-12)
    assert other.extent == pytest.approx(camera.extent)
    camera.zoom(1e9, points)
    assert camera.extent == 0.5
    before = camera.state()
    camera.zoom(10, points)
    assert camera.state() == before
    camera.zoom(1e-9, points)
    assert camera.extent == 1e6


def test_zoom_does_not_clip_geometry_in_front_of_or_behind_orbit_plane():
    camera, points = camera_and_points([[-1, -1, -500], [1, 1, 500]])
    camera.zoom(1e6, points)
    projected = (
        np.column_stack([points, np.ones(len(points))]) @ camera.matrix(100, 100).T
    )
    assert np.max(abs(projected[:, 2])) < 1
