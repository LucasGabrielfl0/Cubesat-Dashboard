from PyQt6.QtWidgets import QLabel
from pyqtgraph.opengl import GLViewWidget, GLMeshItem, MeshData, GLLinePlotItem, GLScatterPlotItem
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import numpy as np

class CubeWidget3D(GLViewWidget):
    def __init__(self, parent=None, show_face_markers=True):
        super().__init__(parent)
        self.setCameraPosition(distance=300, azimuth=45, elevation=30)
        self.opts['distance'] = 400
        self.setBackgroundColor((10, 10, 20))

        # === Cube (Cyan + Transparent) ===
        self.mesh = GLMeshItem(
            meshdata=self.create_cube_mesh(),
            color=(0, 1, 1, 0.4),
            smooth=False,
            shader='shaded',
            drawEdges=True
        )
        self.addItem(self.mesh)

        # === 2U Separation Line ===
        self.separator = self.create_separator_plane(scale=50.0)
        self.addItem(self.separator)

        # === Reference axes (lighter RGB) ===
        ref_colors = [(1, 0.6, 0.6, 1), (0.6, 1, 0.6, 1), (0.6, 0.6, 1, 1)]
        self.ref_axes = self.create_axes(length=150, colors=ref_colors)
        for a in self.ref_axes:
            self.addItem(a)

        # === Overlay 2D labels for X/Y/Z ===
        self.label_X = QLabel("X", self)
        self.label_Y = QLabel("Y", self)
        self.label_Z = QLabel("Z", self)
        self._init_ref_labels_style()

        # === Body axes (solid RGB) ===
        self.body_axes = self.create_axes(length=100)
        for a in self.body_axes:
            self.addItem(a)

        # === Setpoint axes (semi-transparent RGB, dashed) ===
        self.setpoint_axes = self.create_axes(length=100, alpha=0.4, dashed=True)
        for a in self.setpoint_axes:
            self.addItem(a)

        # === Face markers ===
        self._face_items = []
        if show_face_markers:
            self.face_markers_yp = self._create_led_dots()
            for m in self.face_markers_yp:
                self.addItem(m)

            self.face_circle_ym_fill, self.face_circle_ym_outline = self._create_face_circle(face='ym')
            self.face_antenna_fill,   self.face_antenna_outline   = self._create_antenna_square()
            for item in [self.face_circle_ym_fill, self.face_circle_ym_outline,
                         self.face_antenna_fill,   self.face_antenna_outline]:
                self.addItem(item)

            self.face_circle_xp_fill, self.face_circle_xp_outline = self._create_face_circle(face='xp')
            for item in [self.face_circle_xp_fill, self.face_circle_xp_outline]:
                self.addItem(item)

            self._face_items = (
                self.face_markers_yp +
                [self.face_circle_ym_fill, self.face_circle_ym_outline,
                 self.face_antenna_fill,   self.face_antenna_outline,
                 self.face_circle_xp_fill, self.face_circle_xp_outline]
            )

        # === State ===
        self.roll = self.pitch = self.yaw = 0.0
        self.roll_sp = self.pitch_sp = self.yaw_sp = 0.0

    def _init_ref_labels_style(self):
        font = QFont("Arial", 12, QFont.Weight.Bold)
        for lbl, color in [(self.label_X, "rgba(255,100,100,1)"), (self.label_Y, "rgba(100,255,100,1)"), (self.label_Z, "rgba(100,100,255,1)")]:
            lbl.setFont(font)
            lbl.setStyleSheet(f"color: {color}; background: transparent;")
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lbl.show()

    # ------------------------------
    def create_cube_mesh(self):
        scale = 50.0
        verts = np.array([
            [-1, -1, -2], [1, -1, -2], [1, 1, -2], [-1, 1, -2],
            [-1, -1,  2], [1, -1,  2], [1, 1,  2], [-1, 1,  2]
        ], dtype=np.float32) * scale

        faces = np.array([
            [0, 1, 2], [0, 2, 3],
            [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4],
            [2, 3, 7], [2, 7, 6],
            [1, 2, 6], [1, 6, 5],
            [0, 3, 7], [0, 7, 4]
        ])
        return MeshData(vertexes=verts, faces=faces)

    # ------------------------------
    def create_axes(self, length=100.0, colors=None, alpha=1.0, dashed=False):
        axes = []
        default_colors = [(1, 0, 0, alpha), (0, 1, 0, alpha), (0, 0, 1, alpha)]
        colors = colors if colors is not None else default_colors
        dirs = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        origin = np.array([0, 0, 0], dtype=np.float32)

        for i in range(3):
            color = colors[i]
            if dashed:
                segs = 10
                pts = []
                for j in range(segs):
                    start = origin + dirs[i] * length * (j / segs)
                    end = origin + dirs[i] * length * ((j + 0.5) / segs)
                    pts.append(np.vstack([start, end]))
                pts = np.vstack(pts).astype(np.float32)
            else:
                pts = np.vstack([origin, dirs[i] * length]).astype(np.float32)

            line = GLLinePlotItem(pos=pts, color=color, width=3, antialias=True, mode='lines')
            axes.append(line)

        return axes

    # ------------------------------
    def create_separator_plane(self, scale=50.0):
        z = 0.0
        half = 1.0 * scale
        pts = np.array([
            [-half, -half, z],
            [ half, -half, z],
            [ half,  half, z],
            [-half,  half, z],
            [-half, -half, z],
        ], dtype=np.float32)
        return GLLinePlotItem(pos=pts, color=(1, 1, 1, 0.6), width=2, antialias=True, mode='line_strip')

    # ------------------------------
    def _make_circle_pts(self, cx, cy, cz, r, n, axis):
        t = np.linspace(0, 2 * np.pi, n + 1)
        if axis == 'y':
            xs = cx + r * np.cos(t)
            ys = np.full(n + 1, cy)
            zs = cz + r * np.sin(t)
        elif axis == 'x':
            xs = np.full(n + 1, cx)
            ys = cy + r * np.cos(t)
            zs = cz + r * np.sin(t)
        return np.column_stack([xs, ys, zs]).astype(np.float32)

    def _filled_circle(self, cx, cy, cz, r, n, axis):
        """Filled circle using a grid of quads clipped to circle — balloon shader."""
        steps = 30
        verts = []
        faces = []
        idx = 0
        for i in range(steps):
            for j in range(steps):
                # u, v are the two axes in the plane of the circle
                u0 = -r + (2 * r * i / steps)
                u1 = -r + (2 * r * (i + 1) / steps)
                v0 = -r + (2 * r * j / steps)
                v1 = -r + (2 * r * (j + 1) / steps)
                # skip quads outside circle
                uc = (u0 + u1) / 2
                vc = (v0 + v1) / 2
                if uc*uc + vc*vc > r*r:
                    continue
                if axis == 'y':
                    # u=x, v=z, y=cy constant
                    quad = [
                        [cx + u0, cy, cz + v0],
                        [cx + u1, cy, cz + v0],
                        [cx + u1, cy, cz + v1],
                        [cx + u0, cy, cz + v1],
                    ]
                elif axis == 'x':
                    # u=y, v=z, x=cx constant
                    quad = [
                        [cx, cy + u0, cz + v0],
                        [cx, cy + u1, cz + v0],
                        [cx, cy + u1, cz + v1],
                        [cx, cy + u0, cz + v1],
                    ]
                verts.extend(quad)
                faces.append([idx, idx+1, idx+2])
                faces.append([idx, idx+2, idx+3])
                idx += 4
        verts = np.array(verts, dtype=np.float32)
        faces = np.array(faces, dtype=np.int32)
        md = MeshData(vertexes=verts, faces=faces)
        return GLMeshItem(meshdata=md, color=(0.0, 0.2, 0.25, 1.0), smooth=False, shader='balloon', glOptions='opaque', drawEdges=False)

    def _filled_square(self, cx, cy, cz, hw, hh, axis):
        """Filled square — balloon shader ignores lighting, renders raw color."""
        if axis == 'y':
            verts = np.array([
                [cx - hw, cy, cz - hh],
                [cx + hw, cy, cz - hh],
                [cx + hw, cy, cz + hh],
                [cx - hw, cy, cz + hh],
            ], dtype=np.float32)
        elif axis == 'x':
            verts = np.array([
                [cx, cy - hw, cz - hh],
                [cx, cy + hw, cz - hh],
                [cx, cy + hw, cz + hh],
                [cx, cy - hw, cz + hh],
            ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        md = MeshData(vertexes=verts, faces=faces)
        return GLMeshItem(meshdata=md, color=(0.0, 0.2, 0.25, 1.0), smooth=False, shader='balloon', glOptions='opaque', drawEdges=False)

    def _filled_rect(self, cx, cy, cz, hw, hh):
        """Filled rectangle on Y face — balloon shader."""
        verts = np.array([
            [cx - hw, cy, cz - hh],
            [cx + hw, cy, cz - hh],
            [cx + hw, cy, cz + hh],
            [cx - hw, cy, cz + hh],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        md = MeshData(vertexes=verts, faces=faces)
        return GLMeshItem(meshdata=md, color=(0.0, 0.2, 0.25, 1.0), smooth=False, shader='balloon', glOptions='opaque', drawEdges=False)

    def _filled_rect_x(self, cx, cy, cz, hw, hh):
        """Filled rectangle on X face — balloon shader."""
        verts = np.array([
            [cx, cy - hw, cz - hh],
            [cx, cy + hw, cz - hh],
            [cx, cy + hw, cz + hh],
            [cx, cy - hw, cz + hh],
        ], dtype=np.float32)
        faces = np.array([[0, 1, 2], [0, 2, 3]])
        md = MeshData(vertexes=verts, faces=faces)
        return GLMeshItem(meshdata=md, color=(0.0, 0.2, 0.25, 1.0), smooth=False, shader='balloon', glOptions='opaque', drawEdges=False)

    def _create_led_dots(self):
        s = 50.0
        y = s + 1           # Y+ face
        rect_hw = s * 0.80
        rect_hh = s * 0.25 * 0.80
        z_rect  = s * 1.60
        corner  = s * 0.06
        z_led   = z_rect - rect_hh + s * 0.08
        spacing = s * 0.25
        dot_r   = s * 0.06

        colors = [(0, 1, 0, 1), (1, 0, 0, 1), (0, 0, 1, 1)]
        items = []

        # --- Rounded rectangle dark fill on Y+ face ---
        rect_fill = self._filled_rect(0, y, z_rect, rect_hw, rect_hh)
        items.append(rect_fill)

        # --- Rounded rectangle white outline on Y+ face ---
        def rounded_rect_pts_y(cz, hw, hh, cr, n_corner=10):
            pts = []
            corners = [
                (-hw + cr, cz - hh + cr, -np.pi,    -np.pi/2),
                ( hw - cr, cz - hh + cr, -np.pi/2,   0),
                ( hw - cr, cz + hh - cr,  0,          np.pi/2),
                (-hw + cr, cz + hh - cr,  np.pi/2,   np.pi),
            ]
            for (cx2, cz2, a0, a1) in corners:
                t = np.linspace(a0, a1, n_corner)
                xs = cx2 + cr * np.cos(t)
                zs = cz2 + cr * np.sin(t)
                ys = np.full(len(t), y)
                pts.append(np.column_stack([xs, ys, zs]))
            all_pts = np.vstack(pts)
            return np.vstack([all_pts, all_pts[[0]]]).astype(np.float32)

        rr_pts = rounded_rect_pts_y(z_rect, rect_hw, rect_hh, corner)
        rr = GLLinePlotItem(pos=rr_pts, color=(1, 1, 1, 0.8), width=2, antialias=True, mode='line_strip')
        items.append(rr)

        # --- 3 LED scatter dots on Y+ face ---
        for i, color in enumerate(colors):
            x = (i - 1) * spacing
            dot = GLScatterPlotItem(
                pos=np.array([[x, y, z_led]], dtype=np.float32),
                color=color, size=12, pxMode=True
            )
            items.append(dot)

        # --- White circle outline around each LED ---
        n = 24
        for i in range(3):
            x = (i - 1) * spacing
            t = np.linspace(0, 2 * np.pi, n + 1)
            pts = np.column_stack([
                x + dot_r * np.cos(t),
                np.full(n + 1, y),
                z_led + dot_r * np.sin(t)
            ]).astype(np.float32)
            ring = GLLinePlotItem(pos=pts, color=(1, 1, 1, 0.9), width=1.5, antialias=True, mode='line_strip')
            items.append(ring)

        return items

    def _create_face_circle(self, face='xp'):
        s = 50.0
        r = s * 0.70
        n = 40
        if face == 'xp':   # single circle — left of LED face
            cx, cy, cz, axis = s + 1, 0, -s * 1.0, 'x'
        else:               # ym — opposite of LED face, has antenna square too
            cx, cy, cz, axis = 0, -(s + 1), -s * 1.0, 'y'
        fill = self._filled_circle(cx, cy, cz, r, n, axis)
        outline_pts = self._make_circle_pts(cx, cy, cz, r, n, axis)
        outline = GLLinePlotItem(pos=outline_pts, color=(1, 1, 1, 0.8), width=2, antialias=True, mode='line_strip')
        return fill, outline

    def _create_antenna_square(self):
        s = 50.0
        y = -(s + 1)        # Y- face — opposite of LED face (Y+)
        hw = s * 0.30
        z_center = s * 1.60
        hh = s * 0.25
        fill = self._filled_square(0, y, z_center, hw, hh, 'y')
        pts = np.array([
            [-hw, y, z_center - hh],
            [ hw, y, z_center - hh],
            [ hw, y, z_center + hh],
            [-hw, y, z_center + hh],
            [-hw, y, z_center - hh],
        ], dtype=np.float32)
        outline = GLLinePlotItem(pos=pts, color=(1, 1, 1, 0.8), width=2, antialias=True, mode='line_strip')
        return fill, outline

    # ------------------------------
    def resizeEvent(self, ev):
        w = max(1, self.width())
        h = max(1, self.height())
        self.label_X.move(int(w * 0.18), int(h * 0.78))
        self.label_Y.move(int(w * 0.78), int(h * 0.78))
        self.label_Z.move(int(w * 0.50), int(h * 0.05))
        super().resizeEvent(ev)

    # ------------------------------
    def set_attitude(self, roll, pitch, yaw):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw

        self.mesh.resetTransform()
        self.mesh.rotate(-yaw, 0, 0, 1)
        self.mesh.rotate(-pitch, 0, 1, 0)
        self.mesh.rotate(-roll, 1, 0, 0)

        self.separator.resetTransform()
        self.separator.rotate(-yaw, 0, 0, 1)
        self.separator.rotate(-pitch, 0, 1, 0)
        self.separator.rotate(-roll, 1, 0, 0)

        for axis in self.body_axes:
            axis.resetTransform()
            axis.rotate(-yaw, 0, 0, 1)
            axis.rotate(-pitch, 0, 1, 0)
            axis.rotate(-roll, 1, 0, 0)

        for item in self._face_items:
            item.resetTransform()
            item.rotate(-yaw, 0, 0, 1)
            item.rotate(-pitch, 0, 1, 0)
            item.rotate(-roll, 1, 0, 0)

        self.update()

    # ------------------------------
    def set_setpoint(self, roll_sp, pitch_sp, yaw_sp):
        self.roll_sp, self.pitch_sp, self.yaw_sp = roll_sp, pitch_sp, yaw_sp

        for axis in self.setpoint_axes:
            axis.resetTransform()
            axis.rotate(-yaw_sp, 0, 0, 1)
            axis.rotate(-pitch_sp, 0, 1, 0)
            axis.rotate(-roll_sp, 1, 0, 0)

        self.update()