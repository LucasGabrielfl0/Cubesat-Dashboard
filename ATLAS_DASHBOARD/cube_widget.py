from PyQt6.QtWidgets import QLabel
from pyqtgraph.opengl import GLViewWidget, GLMeshItem, MeshData, GLLinePlotItem
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import numpy as np

class CubeWidget3D(GLViewWidget):
    def __init__(self, parent=None):
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
        self.body_axes = self.create_axes(length=100)  # default RGB
        for a in self.body_axes:
            self.addItem(a)

        # === Setpoint axes (semi-transparent RGB, dashed) ===
        self.setpoint_axes = self.create_axes(length=100, alpha=0.4, dashed=True)
        for a in self.setpoint_axes:
            self.addItem(a)

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
        # Square line at Z = 0
        z = 0.0
        half = 1.0 * scale

        pts = np.array([
            [-half, -half, z],
            [ half, -half, z],
            [ half,  half, z],
            [-half,  half, z],
            [-half, -half, z],  # close loop
        ], dtype=np.float32)

        return GLLinePlotItem(
            pos=pts,
            color=(1, 1, 1, 0.6),
            width=2,
            antialias=True,
            mode='line_strip'
        )

    # ------------------------------
    def resizeEvent(self, ev):
        # Reposition 2D overlay labels proportionally to the widget size
        w = max(1, self.width())
        h = max(1, self.height())
        # Place X near lower-left quarter, Y near lower-right quarter, Z near top-center
        self.label_X.move(int(w * 0.18), int(h * 0.78))
        self.label_Y.move(int(w * 0.78), int(h * 0.78))
        self.label_Z.move(int(w * 0.50), int(h * 0.05))
        super().resizeEvent(ev)

    # ------------------------------
    def set_attitude(self, roll, pitch, yaw):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw

        # Cube + body axes rotation
        self.mesh.resetTransform()
        self.mesh.rotate(yaw, 0, 0, 1)
        self.mesh.rotate(pitch, 0, 1, 0)
        self.mesh.rotate(roll, 1, 0, 0)
        
        #
        self.separator.resetTransform()
        self.separator.rotate(yaw, 0, 0, 1)
        self.separator.rotate(pitch, 0, 1, 0)
        self.separator.rotate(roll, 1, 0, 0)

        for axis in self.body_axes:
            axis.resetTransform()
            axis.rotate(yaw, 0, 0, 1)
            axis.rotate(pitch, 0, 1, 0)
            axis.rotate(roll, 1, 0, 0)

        self.update()

    # ------------------------------
    def set_setpoint(self, roll_sp, pitch_sp, yaw_sp):
        self.roll_sp, self.pitch_sp, self.yaw_sp = roll_sp, pitch_sp, yaw_sp

        for axis in self.setpoint_axes:
            axis.resetTransform()
            axis.rotate(yaw_sp, 0, 0, 1)
            axis.rotate(pitch_sp, 0, 1, 0)
            axis.rotate(roll_sp, 1, 0, 0)

        self.update()
