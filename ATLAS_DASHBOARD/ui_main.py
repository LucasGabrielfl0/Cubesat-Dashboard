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

#
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QMainWindow, QComboBox,
    QFrame, QPushButton, QSizePolicy
)


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


class ValueLabel(QLabel):
    def __init__(self, text="0.00", fixed_width=110):
        super().__init__(text)
        font = QFont("Consolas", 11)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet("color: white; background: transparent; border: none;")
        self.setFixedWidth(fixed_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_value(self, value, suffix=""):
        formatted = f"{value:8.2f}{suffix}"
        self.setText(formatted)


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
        font = QFont("Consolas", 11)
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
        self.data_history = []
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
        self.baud_box = QComboBox()
        self.baud_box.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "250000"])
        self.baud_box.setCurrentText("250000")

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

        cfg_box.addWidget(QLabel("Port:"))
        cfg_box.addWidget(self.port_box)
        cfg_box.addWidget(QLabel("Baud:"))
        cfg_box.addWidget(self.baud_box)
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
        numeric_width = 110

        for axis in ["Roll", "Pitch", "Yaw"]:
            frame = QFrame()
            frame.setStyleSheet("QFrame { border: 1px solid #1E3A5F; background-color: #0A0A14; border-radius: 6px; }")
            col_layout = QVBoxLayout(frame)
            col_layout.setContentsMargins(8, 8, 8, 8)

            title = UnderlinedLabel(axis)
            col_layout.addWidget(title)

            pairs = [
                ("Setpoint:", "°"),
                ("Angle:", "°"),
                ("Accel:", " m/s²"),
                ("Gyro:", " °/s"),
            ]

            label_dict = {}
            for name_text, suffix in pairs:
                row = QHBoxLayout()
                name_lbl = NameLabel(name_text)
                value_lbl = ValueLabel(fixed_width=numeric_width)
                row.addWidget(name_lbl)
                row.addStretch()
                row.addWidget(value_lbl)
                col_layout.addLayout(row)
                label_dict[name_text[:-1]] = (value_lbl, suffix)

            col_layout.addStretch()
            attitude_area.addWidget(frame)
            self.value_labels[axis] = label_dict

        right_layout.addLayout(attitude_area)

        # === Info bar ===
        flight_frame = QFrame()
        flight_frame.setFrameShape(QFrame.Shape.Box)
        flight_frame.setStyleSheet("background-color: #111; color: white; padding:5px;")
        flight_layout = QHBoxLayout(flight_frame)
        info_font = QFont("Arial", 11, QFont.Weight.Bold)

        self.icon_sat = QLabel("🛰️:")
        self.icon_sat.setFont(info_font)
        self.icon_sat.setStyleSheet("color: white;")

        self.text_sat = QLabel("ON")
        self.text_sat.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.text_sat.setStyleSheet("color: #32CD32; margin-right: 10px;")

        flight_layout.addWidget(self.icon_sat)
        flight_layout.addWidget(self.text_sat)

        self.flight_labels = {}
        for label in ["Lat", "Long", "Alt"]:
            lbl = FixedInfoLabel(f"{label}: 0.0000°" if label != "Alt" else f"{label}: 0.0 m")
            flight_layout.addWidget(lbl)
            self.flight_labels[label] = lbl

        flight_layout.addStretch()

        self.setpoint_button = QPushButton("Setpoints")
        self.log_button = QPushButton("Log Data")
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
        baudrate = int(self.baud_box.currentText())
        if self.serial_reader:
            self.serial_reader.reconnect(port, baudrate)
            self.connect_button.setText("Connected!")
            QTimer.singleShot(1500, lambda: self.connect_button.setText("Connect"))

    def closeEvent(self, event):
        if self.serial_reader:
            self.serial_reader.stop()
        event.accept()

    # === Popup & Data ===
    def open_setpoint_popup(self):
        if self.setpoint_popup is None or not hasattr(self.setpoint_popup, 'isVisible'):
            self.setpoint_popup = SetpointPopup(serial_reader=self.serial_reader)
        if not self.setpoint_popup.isVisible():
            self.setpoint_popup.show()
            self.setpoint_popup.raise_()
            self.setpoint_popup.activateWindow()

    def on_serial_data(self, data_list):
        if len(data_list) != 20:
            return
        roll, pitch, yaw = data_list[0:3]
        accx, accy, accz = data_list[3:6]
        gyrox, gyroy, gyroz = data_list[6:9]
        battery = data_list[9]
        temp = data_list[10]
        lat, lon, alt = data_list[11:14]
        roll_sp, pitch_sp, yaw_sp = data_list[14:17]
        valid_flag = int(data_list[18])

        self.data_history.append(data_list)
        if len(self.data_history) > 1000:
            self.data_history.pop(0)

        for axis, values in zip(["Roll", "Pitch", "Yaw"],
                                [(roll_sp, roll, accx, gyrox),
                                 (pitch_sp, pitch, accy, gyroy),
                                 (yaw_sp, yaw, accz, gyroz)]):
            for (key, (lbl, suffix)), val in zip(self.value_labels[axis].items(), values):
                lbl.set_value(val, suffix)

        self.cube_widget.set_attitude(roll, pitch, yaw)
        self.cube_widget.set_setpoint(roll_sp, pitch_sp, yaw_sp)

        self.flight_labels["Lat"].setText(f"Lat: {lat:8.4f}°")
        self.flight_labels["Long"].setText(f"Long: {lon:8.4f}°")
        self.flight_labels["Alt"].setText(f"Alt: {alt:8.1f} m")

        self.battery.setValue(battery)

        self.plots["Roll"].update_plot(roll, roll_sp)
        self.plots["Pitch"].update_plot(pitch, pitch_sp)
        self.plots["Yaw"].update_plot(yaw, yaw_sp)

    def save_csv(self):
        folder = "FlightLog"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Odyssey_Log.csv")
        headers = [
            "Roll", "Pitch", "Yaw", "AccX", "AccY", "AccZ",
            "GyroX", "GyroY", "GyroZ", "Battery", "Temperature",
            "Latitude", "Longitude", "Altitude",
            "Roll_Setpoint", "Pitch_Setpoint", "Yaw_Setpoint",
            "Timestamp", "Validity", "CRC"
        ]
        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(self.data_history)
            print(f"[INFO] Saved {len(self.data_history)} samples to {path}")
            self.log_button.setText("Saved!")
            QTimer.singleShot(1000, lambda: self.log_button.setText("Log Data"))
        except Exception as e:
            print(f"[ERROR] Saving CSV: {e}")