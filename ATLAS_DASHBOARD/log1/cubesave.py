from PyQt6.QtWidgets import QLabel
from pyqtgraph.opengl import GLViewWidget, GLMeshItem, MeshData, GLLinePlotItem
from PyQt6.QtGui import QFont
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

        # === Reference axes (lighter RGB) ===
        ref_colors = [(1, 0.6, 0.6, 1), (0.6, 1, 0.6, 1), (0.6, 0.6, 1, 1)]
        self.ref_axes = self.create_axes(length=150, colors=ref_colors)
        for a in self.ref_axes:
            self.addItem(a)

        # === Overlay 2D labels for X/Y/Z ===
        self.create_ref_labels()

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

    # ------------------------------
    def create_cube_mesh(self):
        scale = 50.0
        verts = np.array([
            [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
            [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
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
        """
        Create 3 axes (X, Y, Z) as GLLinePlotItem.
        - colors: list of 3 RGBA tuples (X, Y, Z). Defaults to solid RGB.
        - dashed: bool, whether to render dashed lines.
        - alpha: float, opacity multiplier.
        """
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
    def create_ref_labels(self):
        """
        Create 2D QLabel overlays for static reference axes X/Y/Z.
        They are positioned manually on the GLViewWidget.
        """
        font = QFont("Arial", 12, QFont.Weight.Bold)

        # X-axis label
        self.label_X = QLabel("X", self)
        self.label_X.setStyleSheet("color: rgba(255,100,100,100); background: transparent;")
        self.label_X.setFont(font)
        self.label_X.move(100, 280)  # adjust as needed

        # Y-axis label
        self.label_Y = QLabel("Y", self)
        self.label_Y.setStyleSheet("color: rgba(100,255,100,100); background: transparent;")
        self.label_Y.setFont(font)
        self.label_Y.move(480, 280)  # adjust as needed

        # Z-axis label
        self.label_Z = QLabel("Z", self)
        self.label_Z.setStyleSheet("color: rgba(100,100,255,100); background: transparent;")
        self.label_Z.setFont(font)
        self.label_Z.move(280, 5)  # adjust as needed

        # Make sure they are visible
        for lbl in [self.label_X, self.label_Y, self.label_Z]:
            lbl.show()

    # ------------------------------
    def set_attitude(self, roll, pitch, yaw):
        self.roll, self.pitch, self.yaw = roll, pitch, yaw

        # Cube + body axes rotation
        self.mesh.resetTransform()
        self.mesh.rotate(yaw, 0, 0, 1)
        self.mesh.rotate(pitch, 0, 1, 0)
        self.mesh.rotate(roll, 1, 0, 0)

        for axis in self.body_axes:
            axis.resetTransform()
            axis.rotate(yaw, 0, 0, 1)
            axis.rotate(pitch, 0, 1, 0)
            axis.rotate(roll, 1, 0, 0)

        self.update()

    # ------------------------------
    def set_setpoint(self, roll_sp, pitch_sp, yaw_sp):
        """Update the semi-transparent Setpoint frame orientation."""
        self.roll_sp, self.pitch_sp, self.yaw_sp = roll_sp, pitch_sp, yaw_sp

        for axis in self.setpoint_axes:
            axis.resetTransform()
            axis.rotate(yaw_sp, 0, 0, 1)
            axis.rotate(pitch_sp, 0, 1, 0)
            axis.rotate(roll_sp, 1, 0, 0)

        self.update()
