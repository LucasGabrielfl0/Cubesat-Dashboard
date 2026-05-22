# 
from battery_bar import BatteryBar
from plot_widget import AxisPlot
from cube_widget import CubeWidget3D
from setpoint_popup import SetpointPopup

#
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QColor, QPainter
from PyQt6.QtCore import Qt
from PyQt6.QtCore import Qt, QTimer

#
import os
import csv
from collections import deque

#
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QMainWindow, QComboBox,
    QFrame, QPushButton, QSizePolicy
)

# ===================== DEFINES ===================== #
DATA_HISTORY_MAX = 1000      # Number of telemetry samples stored in memory / saved to CSV
                             # At 10 Hz → 1000 samples = 100 seconds of history
# =================================================== #

class UnderlinedLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("color: #00FFFF; background: transparent;")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#00FFFF"))
        pen.setWidth(2)
        painter.setPen(pen)
        text_rect = self.fontMetrics().boundingRect(self.text())
        x = (self.width() - text_rect.width()) // 2
        y = text_rect.height() + 6
        painter.drawLine(x, y, x + text_rect.width(), y)


class ValueLabel(QWidget):
    NUM_WIDTH  = 74
    UNIT_WIDTH = 36

    def __init__(self):
        super().__init__()
        font = QFont("Consolas", 11)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._num_lbl = QLabel("   0.00")
        self._num_lbl.setFont(font)
        self._num_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._num_lbl.setStyleSheet("color: white; background: transparent; border: none;")
        self._num_lbl.setFixedWidth(self.NUM_WIDTH)

        self._unit_lbl = QLabel("")
        self._unit_lbl.setFont(font)
        self._unit_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._unit_lbl.setStyleSheet("color: #888888; background: transparent; border: none; padding-left: 3px;")
        self._unit_lbl.setFixedWidth(self.UNIT_WIDTH)

        layout.addWidget(self._num_lbl)
        layout.addWidget(self._unit_lbl)
        self.setFixedWidth(self.NUM_WIDTH + self.UNIT_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_value(self, value, suffix="", decimals=2):
        fmt = f"{{value:{8}.{decimals}f}}"
        self._num_lbl.setText(fmt.format(value=value))
        self._unit_lbl.setText(suffix.strip())


class NameLabel(QLabel):
    def __init__(self, text):
        super().__init__(text)
        font = QFont("Arial", 11, QFont.Weight.Medium)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("color: #B0B0B0; background: transparent; border: none;")


class FixedInfoLabel(QLabel):
    def __init__(self, text, fixed_width=130):
        super().__init__(text)
        font = QFont("Consolas", 9)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setFixedWidth(fixed_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("color: white; background: transparent; border: none;")


class MainWindow(QMainWindow):
    def __init__(self, serial_reader=None):
        super().__init__()
        self.serial_reader = serial_reader
        self.setWindowTitle("ATLAS-GroundStation")
        self.showFullScreen()
        self.data_history = deque(maxlen=DATA_HISTORY_MAX)
        self.last_validity = 1
        self.setpoint_popup = None
        self.initUI()

        if self.serial_reader:
            self.serial_reader.data_received.connect(self.on_serial_data)

    def initUI(self):
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        left_layout = QVBoxLayout()
        self.plots = {}
        for axis in ["Roll", "Pitch", "Yaw"]:
            pw = AxisPlot(axis_name=axis)
            left_layout.addWidget(pw)
            self.plots[axis] = pw

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setSpacing(8)

        # === Top bar ===
        top_box = QHBoxLayout()
        banner = QLabel()
        pixmap = QPixmap("Figures/AsaBanner.png")
        if not pixmap.isNull():
            banner.setPixmap(pixmap.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation))
        banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_box.addWidget(banner)

        cfg_box = QHBoxLayout()
        self.port_box = QComboBox()
        self.port_box.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6"])
        self.port_box.setCurrentText("COM6")
        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedHeight(28)
        self.connect_button.setFixedWidth(80)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005999; }
            QPushButton:pressed { background-color: #003F73; }
        """)
        self.connect_button.clicked.connect(self.reconnect_serial)

        baud_lbl_key = QLabel("Baud:")
        baud_lbl_key.setStyleSheet("color: #B0B0B0;")
        baud_lbl_val = QLabel("250000")
        baud_lbl_val.setStyleSheet("color: white; font-weight: bold;")
        cfg_box.addWidget(QLabel("Port:"))
        cfg_box.addWidget(self.port_box)
        cfg_box.addWidget(baud_lbl_key)
        cfg_box.addWidget(baud_lbl_val)
        cfg_box.addWidget(self.connect_button)

        self.battery = BatteryBar()
        self.battery.setFixedSize(140, 55)

        self.close_button = QPushButton("X")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #AA0000;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #CC0000; }
            QPushButton:pressed { background-color: #770000; }
        """)
        self.close_button.clicked.connect(self.close)

        top_box.addLayout(cfg_box)
        top_box.addWidget(self.battery)
        top_box.addWidget(self.close_button)
        right_layout.addLayout(top_box)

        # === Attitude boxes ===
        attitude_area = QHBoxLayout()
        attitude_area.setSpacing(14)
        self.value_labels = {}

        for axis in ["Roll", "Pitch", "Yaw"]:
            frame = QFrame()
            frame.setStyleSheet("QFrame { border: 1px solid #1E3A5F; background-color: #0A0A14; border-radius: 6px; }")
            col_layout = QVBoxLayout(frame)
            col_layout.setContentsMargins(8, 8, 8, 8)

            title = UnderlinedLabel(axis)
            col_layout.addWidget(title)

            pairs = [
                ("Angle:",    "°",    2),
                ("Setpoint:", "°",    2),
                ("Accel:",    "g",    3),
                ("Gyro:",     "°/s",  2),
            ]

            label_dict = {}
            for name_text, suffix, decimals in pairs:
                row = QHBoxLayout()
                row.setSpacing(4)
                name_lbl = NameLabel(name_text)
                value_lbl = ValueLabel()
                value_lbl.set_value(0.0, suffix, decimals)
                row.addWidget(name_lbl)
                row.addStretch()
                row.addWidget(value_lbl)
                col_layout.addLayout(row)
                label_dict[name_text[:-1]] = (value_lbl, suffix, decimals)

            col_layout.addStretch()
            attitude_area.addWidget(frame)
            self.value_labels[axis] = label_dict

        right_layout.addLayout(attitude_area)

        # === Info bar ===
        flight_frame = QFrame()
        flight_frame.setFrameShape(QFrame.Shape.Box)
        flight_frame.setStyleSheet("background-color: #111; color: white; padding:5px;")
        flight_layout = QHBoxLayout(flight_frame)

        self.temp_label    = FixedInfoLabel("Temperature:  0.0 °C", fixed_width=152)
        self.battery_label = FixedInfoLabel("Battery: 0.00 V",      fixed_width=112)
        self.status_label  = FixedInfoLabel("Status: 0",            fixed_width=82)
        flight_layout.addWidget(self.temp_label)
        flight_layout.addWidget(self.battery_label)
        flight_layout.addWidget(self.status_label)
        flight_layout.addStretch()

        self.setpoint_button = QPushButton("Setpoints")
        self.log_button      = QPushButton("Log Data")
        for btn in [self.setpoint_button, self.log_button]:
            btn.setFixedHeight(30)
            btn.setFixedWidth(100)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #007ACC;
                    color: white;
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 15px;
                }
                QPushButton:hover { background-color: #005999; }
                QPushButton:pressed { background-color: #003F73; }
            """)

        self.setpoint_button.clicked.connect(self.open_setpoint_popup)
        self.log_button.clicked.connect(self.save_csv)
        flight_layout.addWidget(self.setpoint_button)
        flight_layout.addWidget(self.log_button)
        right_layout.addWidget(flight_frame)

        right_layout.addStretch()

        # === Cube title and model ===
        font_id = QFontDatabase.addApplicationFont("Fonts/Orbitron-Bold.ttf")
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        orbitron_font = QFont(font_families[0], 20, QFont.Weight.Bold) if font_families else QFont("Arial", 20, QFont.Weight.Bold)

        cube_title_frame = QFrame()
        cube_title_frame.setFrameShape(QFrame.Shape.Box)
        cube_title_frame.setStyleSheet("background-color: #0A0A14; color: white;")
        cube_title_label = QLabel("ODYSSEY-01")
        cube_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cube_title_label.setFont(orbitron_font)
        cube_title_label.setStyleSheet("color: white; letter-spacing: 2px;")
        frame_layout = QVBoxLayout(cube_title_frame)
        frame_layout.addWidget(cube_title_label)
        right_layout.addWidget(cube_title_frame)

        self.cube_widget = CubeWidget3D()
        self.cube_widget.setMinimumHeight(250)
        right_layout.addWidget(self.cube_widget, stretch=2)

        main_layout.addLayout(left_layout, stretch=3)
        main_layout.addWidget(right_container, stretch=1)

    # === Serial control ===
    def reconnect_serial(self):
        port     = self.port_box.currentText()
        baudrate = 250000
        if self.serial_reader:
            self.serial_reader.reconnect(port, baudrate)
            self.connect_button.setText("Connected!")
            QTimer.singleShot(1500, lambda: self.connect_button.setText("Connect"))

    def closeEvent(self, event):
        if self.serial_reader:
            self.serial_reader.stop()
        event.accept()

    # === Popup ===
    def open_setpoint_popup(self):
        if self.setpoint_popup is None or not hasattr(self.setpoint_popup, 'isVisible'):
            self.setpoint_popup = SetpointPopup(serial_reader=self.serial_reader)
        if not self.setpoint_popup.isVisible():
            self.setpoint_popup.show()
            self.setpoint_popup.raise_()
            self.setpoint_popup.activateWindow()

    # === Main data handler ===
    def on_serial_data(self, data_list):
        if len(data_list) != 20:
            return

        roll, pitch, yaw          = data_list[0:3]
        accx, accy, accz          = data_list[3:6]
        gyrox, gyroy, gyroz       = data_list[6:9]
        battery                   = data_list[9]
        temp                      = data_list[10]
        lat, lon, alt             = data_list[11:14]
        roll_sp, pitch_sp, yaw_sp = data_list[14:17]

        # deque handles maxlen automatically — no pop(0) needed
        self.data_history.append({
            "MsgCounter":  int(data_list[17]),
            "Roll":        roll,    "Pitch":    pitch,    "Yaw":    yaw,
            "Roll_SP":     roll_sp, "Pitch_SP": pitch_sp, "Yaw_SP": yaw_sp,
            "AccX":        accx,    "AccY":     accy,     "AccZ":   accz,
            "GyroX":       gyrox,   "GyroY":    gyroy,    "GyroZ":  gyroz,
            "Battery":     battery, "Temperature": temp,
            "Longitude":   lon,     "Latitude":    lat,
        })

        # Attitude value labels
        for axis, values in zip(["Roll", "Pitch", "Yaw"],
                                [(roll,  roll_sp,  accx, gyrox),
                                 (pitch, pitch_sp, accy, gyroy),
                                 (yaw,   yaw_sp,   accz, gyroz)]):
            for (key, (lbl, suffix, decimals)), val in zip(self.value_labels[axis].items(), values):
                lbl.set_value(val, suffix, decimals)

        # 3D cube
        self.cube_widget.set_attitude(roll, pitch, yaw)
        self.cube_widget.set_setpoint(roll_sp, pitch_sp, yaw_sp)

        # Plots
        self.plots["Roll"].update_plot(roll, roll_sp)
        self.plots["Pitch"].update_plot(pitch, pitch_sp)
        self.plots["Yaw"].update_plot(yaw, yaw_sp)

        # HK labels
        self.temp_label.setText(f"Temperature: {temp:5.1f} °C")
        self.battery_label.setText(f"Battery: {battery:.2f} V")
        self.status_label.setText(f"Status: {int(data_list[13])}")
        self.battery.setValue(min(100.0, max(0.0, ((battery - 6.0) / (8.40 - 6.0)) * 100.0)))

    def save_csv(self):
        folder = "FlightLog"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Odyssey_Log.csv")

        columns = [
            ("MsgCounter",     "MsgCounter",  "d"),
            ("Roll",           "Roll",        ".2f"),
            ("Pitch",          "Pitch",       ".2f"),
            ("Yaw",            "Yaw",         ".2f"),
            ("Roll_Setpoint",  "Roll_SP",     ".2f"),
            ("Pitch_Setpoint", "Pitch_SP",    ".2f"),
            ("Yaw_Setpoint",   "Yaw_SP",      ".2f"),
            ("AccX",           "AccX",        ".3f"),
            ("AccY",           "AccY",        ".3f"),
            ("AccZ",           "AccZ",        ".3f"),
            ("GyroX",          "GyroX",       ".2f"),
            ("GyroY",          "GyroY",       ".2f"),
            ("GyroZ",          "GyroZ",       ".2f"),
            ("Battery",        "Battery",     ".2f"),
            ("Temperature",    "Temperature", ".1f"),
            ("Longitude",      "Longitude",   ".7f"),
            ("Latitude",       "Latitude",    ".7f"),
        ]

        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([col[0] for col in columns])
                for sample in self.data_history:
                    writer.writerow([format(sample[key], fmt) for _, key, fmt in columns])
            print(f"[INFO] Saved {len(self.data_history)} samples to {path}")
            self.log_button.setText("Saved!")
            QTimer.singleShot(1000, lambda: self.log_button.setText("Log Data"))
        except Exception as e:
            print(f"[ERROR] Saving CSV: {e}")