from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np

class AxisPlot(QWidget):
    # Y-axis ranges per axis name
    Y_RANGES = {
        "Roll":  (-180, 180),
        "Pitch": (-90,   90),
        "Yaw":   (0,    360),
    }

    def __init__(self, axis_name="Axis", max_points=600):
        super().__init__()
        self.axis_name = axis_name
        self.max_points = max_points  # 60s at 10Hz = 600 points

        self.data_current = np.zeros(self.max_points)
        self.data_setpoint = np.zeros(self.max_points)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        y_min, y_max = self.Y_RANGES.get(axis_name, (-180, 180))

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.5)
        self.plot_widget.setYRange(y_min, y_max)
        self.plot_widget.setXRange(0, self.max_points)
        self.plot_widget.setLabel('left', axis_name)
        self.plot_widget.addLegend(offset=(10,10))

        # Current = green, Setpoint = red
        self.curve_current = self.plot_widget.plot(self.data_current, pen=pg.mkPen('g', width=2), name="Current")
        self.curve_setpoint = self.plot_widget.plot(self.data_setpoint, pen=pg.mkPen('r', width=2), name="Setpoint")
        layout.addWidget(self.plot_widget)

    def update_plot(self, current_value, setpoint_value):
        # Shift data
        self.data_current = np.roll(self.data_current, -1)
        self.data_setpoint = np.roll(self.data_setpoint, -1)
        self.data_current[-1] = current_value
        self.data_setpoint[-1] = setpoint_value
        self.curve_current.setData(self.data_current)
        self.curve_setpoint.setData(self.data_setpoint)