"""A small instanced LDraw renderer, usable with Qt or a standalone GL context."""

import math

import moderngl
import numpy as np
from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QSurfaceFormat
from PySide6.QtOpenGL import QOpenGLWindow

from pyblocks.core.ldraw import box_corners, rgba
from pyblocks.core.lessons import camera_values

VERTEX = """
#version 330
uniform mat4 camera;
uniform float step;
uniform bool overlay;
uniform bool future;
uniform ivec2 group;
in vec3 position;
in vec4 color;
in mat4 model;
in vec4 tint;
in float added;
in float identity;
in float highlighted;
out vec4 shade;
out vec3 world;
flat out int object_id;
flat out int state;
flat out int selected;
void main() {
    world = (model * vec4(position, 1)).xyz;
    gl_Position = camera * vec4(world, 1);
    object_id = int(identity);
    selected = int(highlighted);
    state = added > step ? 2 : (added < step ? 0 : 1);
    if (object_id < group.x || object_id > group.y || (overlay && selected == 0))
        gl_Position = vec4(2,2,2,1);
    shade = color.a < 0 ? tint : color;
    if (state == 0) shade.rgb = mix(shade.rgb, vec3(.88, .90, .93), .35);
    if (selected != 0) shade.rgb = mix(shade.rgb, vec3(1, .64, .04), .6);
}
"""
FRAGMENT = """
#version 330
uniform bool picking;
uniform bool overlay;
in vec4 shade;
in vec3 world;
flat in int object_id;
flat in int state;
flat in int selected;
out vec4 pixel;
void main() {
    if (state == 2 || (overlay && selected == 0)) discard;
    if (picking) {
        pixel = vec4(float(object_id & 255), float((object_id >> 8) & 255),
                     float((object_id >> 16) & 255), 255) / 255;
    } else {
        vec3 normal = cross(dFdx(world), dFdy(world));
        float length2 = dot(normal, normal);
        float light = length2 > 0 ? .65 + .35 * abs(dot(normal * inversesqrt(length2), normalize(vec3(1,-2,3)))) : 1;
        pixel = vec4(shade.rgb * light, overlay ? .35 : 1);
    }
}
"""
EDGE_VERTEX = """
#version 330
uniform mat4 camera;
uniform float step;
uniform bool overlay;
uniform bool future;
uniform ivec2 group;
in vec3 a;
in vec3 b;
in vec3 c;
in vec3 d;
in vec4 color;
in mat4 model;
in vec4 tint;
in float added;
in float identity;
in float highlighted;
out vec4 shade;
flat out int visible;
void main() {
    mat4 m = camera * model;
    vec4 pa = m * vec4(a,1), pb = m * vec4(b,1);
    vec2 axis = pb.xy / pb.w - pa.xy / pa.w;
    vec4 pc = m * vec4(c,1), pd = m * vec4(d,1);
    vec2 u = pc.xy / pc.w - pa.xy / pa.w, v = pd.xy / pd.w - pa.xy / pa.w;
    float side1 = axis.x * u.y - axis.y * u.x;
    float side2 = axis.x * v.y - axis.y * v.x;
    visible = side1 * side2 >= -1e-12 && (future || added <= step) ? 1 : 0;
    if (int(identity) < group.x || int(identity) > group.y) visible = 0;
    shade = color.a < 0 ? vec4(tint.rgb * .3, 1) : color;
    if (added > step) shade = vec4(.77,.79,.82,1);
    else if (added == step) shade.rgb = mix(shade.rgb, vec3(.06,.32,.7), .35);
    if (overlay && (highlighted == 0 || added > step)) visible = 0;
    if (highlighted != 0) shade = vec4(.85,.32,0,1);
    gl_Position = gl_VertexID % 2 == 0 ? pa : pb;
    gl_Position.z -= .00015 * gl_Position.w;
}
"""
EDGE_FRAGMENT = """
#version 330
in vec4 shade;
flat in int visible;
out vec4 pixel;
void main() { if (visible == 0) discard; pixel = shade; }
"""


class Camera:
    def __init__(self, bounds):
        self.clip_center = np.mean(bounds, axis=0)
        self.clip_radius = max(float(np.linalg.norm(bounds[1] - bounds[0])) / 2, 1.0)
        self.fit(bounds)

    def fit(self, bounds, aspect=1.0):
        self.center = np.mean(bounds, axis=0).astype(float)
        self.yaw, self.pitch = 35.0, 25.0
        projected = box_corners(bounds) @ np.array(self.basis()).T
        self.extent = (
            max(
                float(np.ptp(projected[:, 0])) / aspect,
                float(np.ptp(projected[:, 1])),
                1.0,
            )
            * 0.58
        )

    def center_on(self, points):
        basis = np.array(self.basis())
        projected = points @ basis.T
        self.center = (projected.min(axis=0) + projected.max(axis=0)) / 2 @ basis

    def zoom(self, factor, points, aspect=1.0):
        """Zoom about the current center, holding endangered outer edges in place.

        Correction is bounded by zoom motion, including after a manual pan outside
        the viewport. It stops at the selection center and never runs on zoom-out.
        """
        extent = max(0.5, min(1e6, self.extent / factor))
        if extent < self.extent and len(points):
            basis = np.array(self.basis())[:2]
            projected = (points - self.center) @ basis.T
            low, high = projected.min(axis=0), projected.max(axis=0)
            middle = (low + high) / 2
            far = np.abs(middle) + (high - low) / 2
            limit = 0.9 * extent * np.array([aspect, 1.0])
            shift = np.minimum(
                np.abs(middle),
                np.minimum(
                    np.maximum(far - limit, 0),
                    (1 - extent / self.extent) * far,
                ),
            )
            self.center += (np.sign(middle) * shift) @ basis
        self.extent = extent

    def basis(self):
        yaw, pitch = np.radians([self.yaw, self.pitch])
        back = np.array(
            [
                math.cos(pitch) * math.sin(yaw),
                -math.sin(pitch),
                math.cos(pitch) * math.cos(yaw),
            ]
        )
        right = np.cross([0.0, -1.0, 0.0], back)
        right /= np.linalg.norm(right)
        return right, np.cross(back, right), back

    def matrix(self, width, height):
        view = np.eye(4)
        view[:3, :3] = self.basis()
        view[:3, 3] = -view[:3, :3] @ self.center
        # Close-up zoom must not clip parts far from the orbit plane.
        depth = abs((self.clip_center - self.center) @ view[2, :3]) + self.clip_radius
        projection = np.diag(
            [
                height / max(width, 1) / self.extent,
                1 / self.extent,
                -1 / (depth * 1.01),
                1,
            ]
        )
        return projection @ view

    def state(self):
        return dict(
            center=self.center.tolist(),
            extent=self.extent,
            yaw=self.yaw,
            pitch=self.pitch,
        )

    def restore(self, state):
        values = np.array(camera_values(state), dtype=float)
        self.center = values[:3]
        self.extent, self.yaw, self.pitch = map(float, values[3:])


class Renderer:
    def __init__(self, ctx, scene):
        self.ctx, self.scene = ctx, scene
        self.faces = ctx.program(vertex_shader=VERTEX, fragment_shader=FRAGMENT)
        self.edges = ctx.program(
            vertex_shader=EDGE_VERTEX, fragment_shader=EDGE_FRAGMENT
        )
        self.resources = [self.faces, self.edges]
        self.batches = []
        self.selection_buffers = []
        self.selection = frozenset()
        for name, mesh in scene.meshes.items():
            objects = [
                (i + 1, item)
                for i, item in enumerate(scene.instances)
                if item.part == name
            ]
            instance_data = np.array(
                [
                    [
                        *item.transform.T.ravel(),
                        *rgba(item.color, scene.colors),
                        item.step,
                        index,
                    ]
                    for index, item in objects
                ],
                dtype="f4",
            )
            instances = ctx.buffer(instance_data.tobytes())
            selected = ctx.buffer(np.zeros(len(objects), dtype="f4").tobytes())
            self.selection_buffers.append((selected, [index for index, _ in objects]))
            self.resources.extend([instances, selected])
            selection_format = (selected, "1f /i", "highlighted")
            instance_format = (
                instances,
                "16f 4f 1f 1f /i",
                "model",
                "tint",
                "added",
                "identity",
            )
            face_colors = np.array(
                [
                    (
                        (-1.0, -1.0, -1.0, -1.0)
                        if code == 16
                        else rgba(int(code), scene.colors)
                    )
                    for code in mesh.colors
                ],
                dtype="f4",
            ).reshape(-1, 4)
            if len(mesh.triangles):
                vertices = np.concatenate(
                    [mesh.triangles.reshape(-1, 3), np.repeat(face_colors, 3, axis=0)],
                    axis=1,
                ).astype("f4")
                buffer = ctx.buffer(vertices.tobytes())
                vao = ctx.vertex_array(
                    self.faces,
                    [
                        (buffer, "3f 4f", "position", "color"),
                        instance_format,
                        selection_format,
                    ],
                )
                self.resources.extend([buffer, vao])
                self.batches.append((vao, len(objects), False))
            if len(mesh.lines):

                def edge_color(code):
                    if code in (16, 24):
                        return (-1.0, -1.0, -1.0, -1.0)
                    return (
                        rgba(-int(code) - 1, scene.colors, edge=True)
                        if code < 0
                        else rgba(int(code), scene.colors)
                    )

                colors = np.array([edge_color(c) for c in mesh.line_colors], dtype="f4")
                vertices = np.repeat(
                    np.concatenate([mesh.lines.reshape(-1, 12), colors], axis=1),
                    2,
                    axis=0,
                ).astype("f4")
                buffer = ctx.buffer(vertices.tobytes())
                vao = ctx.vertex_array(
                    self.edges,
                    [
                        (buffer, "3f 3f 3f 3f 4f", "a", "b", "c", "d", "color"),
                        instance_format,
                        selection_format,
                    ],
                )
                self.resources.extend([buffer, vao])
                self.batches.append((vao, len(objects), True))

    def draw(
        self,
        target,
        camera,
        step,
        *,
        selected=(),
        future=False,
        picking=False,
        group=None,
        size=None,
    ):
        selected = frozenset(selected)
        if selected != self.selection:
            for buffer, indices in self.selection_buffers:
                buffer.write(
                    np.array([i in selected for i in indices], dtype="f4").tobytes()
                )
            self.selection = selected
        ctx = self.ctx
        target.use()
        target.depth_mask = True
        ctx.depth_func = "<"
        size = size or target.size
        ctx.viewport = (0, 0, *size)
        ctx.enable_only(moderngl.DEPTH_TEST)
        target.clear(*((0.0, 0.0, 0.0, 0.0) if picking else (0.95, 0.96, 0.98, 1.0)))
        matrix = camera.matrix(*size).T.astype("f4").tobytes()
        for program in (self.faces, self.edges):
            program["camera"].write(matrix)
            program["step"].value = float(step)
            program["overlay"].value = False
            program["group"].value = group or (1, len(self.scene.instances))
            if "future" in program:
                program["future"].value = future
        self.faces["picking"].value = picking
        for vao, count, edge in self.batches:
            if not edge or not picking:
                vao.render(
                    moderngl.LINES if edge else moderngl.TRIANGLES, instances=count
                )

        if selected and not picking:
            # Hidden selected surfaces are translucent; visible surfaces retain
            # lighting. Edges are then drawn on top, including occluded copies.
            target.depth_mask = False
            ctx.enable(moderngl.BLEND)
            # Qt composites this framebuffer as premultiplied alpha. Preserve
            # its opaque alpha while blending RGB, including under QPainter.
            ctx.blend_func = (
                moderngl.SRC_ALPHA,
                moderngl.ONE_MINUS_SRC_ALPHA,
                moderngl.ZERO,
                moderngl.ONE,
            )
            ctx.blend_equation = moderngl.FUNC_ADD
            ctx.depth_func = ">"
            self.faces["overlay"].value = True
            for vao, count, edge in self.batches:
                if not edge:
                    vao.render(moderngl.TRIANGLES, instances=count)
            ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
            self.edges["overlay"].value = True
            for vao, count, edge in self.batches:
                if edge:
                    vao.render(moderngl.LINES, instances=count)
            target.depth_mask = True
            ctx.depth_func = "<"
            ctx.enable(moderngl.DEPTH_TEST)

    def pick(self, size, x, y, camera, step, group=None):
        target = self.ctx.simple_framebuffer(size, components=4)
        try:
            self.draw(target, camera, step, picking=True, group=group)
            rgb = target.read(viewport=(x, y, 1, 1), components=3)
            return rgb[0] | rgb[1] << 8 | rgb[2] << 16
        finally:
            target.release()

    def release(self):
        for resource in reversed(self.resources):
            resource.release()
        self.resources.clear()


class QtContextLoader:
    """Resolve functions through Qt; Qt retains ownership of the native context."""

    def __init__(self, context):
        self.context = context

    def load_opengl_function(self, name):
        return self.context.getProcAddress(name.encode("ascii")) or 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def release(self):
        pass


class LegoView(QOpenGLWindow):
    changed = Signal()
    selected = Signal(str)
    failed = Signal(str)

    def __init__(self, scene, state=None):
        # A contained native surface leaves the Studio window's surface intact
        # when 3D is first opened. Every frame is drawn in full.
        super().__init__()
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        self.setFormat(fmt)
        self.scene = scene
        self.corners = scene.corners()
        self.camera = Camera(scene.bounds())
        if state:
            self.camera.restore(state)
        self.renderer = None
        self.fitted = bool(state)
        self.step = 0
        self.selection = frozenset()
        self.future = False
        self.group = None
        self.marker = None
        self.failure = ""
        self.setMinimumSize(QSize(240, 200))

    def initializeGL(self):
        try:
            # Qt already made its context current. Native auto-detection assumes
            # GLX on Linux, which cannot attach to Qt's Wayland/EGL context.
            ctx = moderngl.create_context(
                require=330, context=QtContextLoader(self.context())
            )
            self.renderer = Renderer(ctx, self.scene)
            self.context().aboutToBeDestroyed.connect(
                self.cleanup, Qt.ConnectionType.DirectConnection
            )
        except Exception as error:
            self.failure = str(error)
            self.failed.emit(self.failure)

    def cleanup(self):
        if self.renderer:
            self.makeCurrent()
            self.renderer.release()
            self.renderer.ctx.release()
            self.renderer = None
            self.doneCurrent()

    def paintGL(self):
        if self.renderer:
            try:
                # The native framebuffer has no texture attachment to query its
                # current size. Qt owns its size, including fractional scaling.
                target = self.renderer.ctx.detect_framebuffer(
                    self.defaultFramebufferObject()
                )
                self.renderer.draw(
                    target,
                    self.camera,
                    self.step,
                    selected=self.selection,
                    future=self.future,
                    group=self.group,
                    size=self.pixel_size(),
                )
                if self.marker:
                    point, label = self.marker
                    position = self.camera.matrix(
                        self.width(), self.height()
                    ) @ np.array([*point, 1.0])
                    center = QPointF(
                        (position[0] + 1) * self.width() / 2,
                        (1 - position[1]) * self.height() / 2,
                    )
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setPen(QPen(QColor("#854300"), 2))
                    painter.setBrush(QColor("#ffcf52"))
                    painter.drawEllipse(center, 12, 12)
                    painter.drawText(center + QPointF(17, 5), label)
                    painter.end()
            except Exception as error:
                if str(error) != self.failure:
                    self.failure = str(error)
                    self.failed.emit(self.failure)

    def resizeGL(self, width, height):
        if not self.fitted and width and height:
            self.camera.fit(self.scene.bounds(), width / height)
            self.fitted = True

    def pixel_size(self):
        scale = self.devicePixelRatio()
        return round(self.width() * scale), round(self.height() * scale)

    def interest_points(self):
        first, last = self.group or (1, len(self.scene.instances))
        indices = [
            i
            for i in range(first - 1, last)
            if self.scene.instances[i].step <= self.step
        ]
        selected = [i for i in indices if i + 1 in self.selection]
        return self.corners[selected or indices].reshape(-1, 3)

    def select(self, identities, *, center=False):
        identities = set(identities)
        selection = frozenset(
            i + 1
            for i, item in enumerate(self.scene.instances)
            if item.identity in identities
        )
        self.selection = selection
        if selection and center:
            points = self.interest_points()
            if len(points):
                self.camera.center_on(points)
                self.fitted = True
                self.changed.emit()
        self.update()

    def mousePressEvent(self, event):
        self.origin = self.previous = event.position()
        self.panning = bool(
            event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton)
            or event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )

    def mouseMoveEvent(self, event):
        if not event.buttons():
            return
        delta = event.position() - self.previous
        self.previous = event.position()
        if self.panning:
            right, up, _ = self.camera.basis()
            self.camera.center -= (
                (delta.x() * right - delta.y() * up)
                * 2
                * self.camera.extent
                / max(self.height(), 1)
            )
        elif event.buttons() & Qt.MouseButton.LeftButton:
            self.camera.yaw += delta.x() * 0.5
            self.camera.pitch = max(-85, min(85, self.camera.pitch + delta.y() * 0.5))
        self.update()

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self.panning
            and (event.position() - self.origin).manhattanLength() < 4
            and self.renderer
        ):
            self.makeCurrent()
            scale = self.devicePixelRatio()
            size = self.pixel_size()
            x = max(0, min(size[0] - 1, round(event.position().x() * scale)))
            y = max(
                0, min(size[1] - 1, size[1] - 1 - round(event.position().y() * scale))
            )
            selected = self.renderer.pick(
                size, x, y, self.camera, self.step, self.group
            )
            self.doneCurrent()
            identity = self.scene.instances[selected - 1].identity if selected else ""
            self.select(
                (identity,),
                center=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier),
            )
            self.selected.emit(identity)
        self.update()
        self.changed.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.select(())
            self.selected.emit("")
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        delta = event.pixelDelta().y() or event.angleDelta().y()
        self.camera.zoom(
            math.exp(delta / 1200),
            self.interest_points(),
            self.width() / max(self.height(), 1),
        )
        self.update()
        self.changed.emit()
