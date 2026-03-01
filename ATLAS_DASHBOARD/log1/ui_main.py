from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMainWindow, QComboBox, QFrame, QPushButton, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QFontMetrics
from PyQt6.QtCore import Qt
import os
import csv
from battery_bar import BatteryBar
from plot_widget import AxisPlot
from cube_widget import CubeWidget3D


class MainWindow(QMainWindow):
    def __init__(self, serial_reader=None):
        super().__init__()
        self.setWindowTitle("ATLAS-GroundStation")
        self.resize(1500, 900)
        self.serial_reader = serial_reader
        self.data_history = []  # Store last 1000 packets for logging
        self.initUI()

        if self.serial_reader is not None:
            self.serial_reader.data_received.connect(self.on_serial_data)

    def initUI(self):
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # ===== LEFT SIDE: GRAPHS =====
        left_layout = QVBoxLayout()
        self.plots = {}
        for axis in ["Roll", "Pitch", "Yaw"]:
            pw = AxisPlot(axis_name=axis)
            left_layout.addWidget(pw)
            self.plots[axis] = pw

        # ===== RIGHT SIDE =====
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        # ===== Banner + Battery + Port Config =====
        top_box = QHBoxLayout()
        banner = QLabel()
        pixmap = QPixmap("AsaBanner.png")
        banner.setPixmap(pixmap.scaledToHeight(60, Qt.TransformationMode.SmoothTransformation))
        banner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_box.addWidget(banner)

        cfg_box = QHBoxLayout()
        self.port_box = QComboBox()
        self.port_box.addItems(["COM1", "COM2", "COM3", "COM4", "COM5"])
        self.port_box.setCurrentText("COM5")
        self.baud_box = QComboBox()
        self.baud_box.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "250000"])
        self.baud_box.setCurrentText("115200")
        cfg_box.addWidget(QLabel("Port:"))
        cfg_box.addWidget(self.port_box)
        cfg_box.addWidget(QLabel("Baud:"))
        cfg_box.addWidget(self.baud_box)

        self.battery = BatteryBar()
        self.battery.setFixedHeight(60)
        top_box.addLayout(cfg_box)
        top_box.addWidget(self.battery)
        right_layout.addLayout(top_box)

        # ===== Roll / Pitch / Yaw Columns =====
        columns_layout = QHBoxLayout()
        font = QFont("Arial", 12, QFont.Weight.Bold)
        self.value_labels = {}

        for axis in ["Roll", "Pitch", "Yaw"]:
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.Box)
            frame.setStyleSheet("background-color: #111; color: white; padding:5px;")
            col_layout = QVBoxLayout(frame)

            title = QLabel(axis)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            title.setStyleSheet("color: cyan;")

            lbl_angle = QLabel("Angle: 0.0°")
            lbl_setpoint = QLabel("Setpoint: 0.0°")
            lbl_acc = QLabel("Accel: 0.0")
            lbl_gyro = QLabel("Gyro: 0.0")

            for lbl in [lbl_angle, lbl_setpoint, lbl_acc, lbl_gyro]:
                lbl.setFont(font)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
                lbl.setStyleSheet("background-color: transparent; color: white;")
                fm = QFontMetrics(font)
                lbl.setFixedWidth(fm.horizontalAdvance("Setpoint: -9999.99°"))

            col_layout.addWidget(title)
            col_layout.addWidget(lbl_angle)
            col_layout.addWidget(lbl_setpoint)
            col_layout.addWidget(lbl_acc)
            col_layout.addWidget(lbl_gyro)
            columns_layout.addWidget(frame)

            self.value_labels[axis] = {
                "Angle": lbl_angle,
                "Setpoint": lbl_setpoint,
                "Accel": lbl_acc,
                "Gyro": lbl_gyro
            }

        right_layout.addLayout(columns_layout)

        # ===== FLIGHT INFO BAR =====
        flight_frame = QFrame()
        flight_frame.setFrameShape(QFrame.Shape.Box)
        flight_frame.setStyleSheet("background-color: #111; color: white; padding:5px;")
        flight_layout = QHBoxLayout(flight_frame)
        info_font = QFont("Arial", 11, QFont.Weight.Bold)
        self.flight_labels = {}

        for label in ["Lat", "Long", "Alt"]:
            lbl = QLabel(f"{label}: 0")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(info_font)
            lbl.setStyleSheet("color: white;")
            flight_layout.addWidget(lbl)
            self.flight_labels[label] = lbl

        # === Log Data Button ===
        self.log_button = QPushButton("Log Data")
        self.log_button.setFixedHeight(30)
        self.log_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #005999; }
        """)
        self.log_button.clicked.connect(self.save_csv)
        flight_layout.addWidget(self.log_button)

        right_layout.addWidget(flight_frame)
        right_layout.addStretch()

        # ===== Cube =====
        font_id = QFontDatabase.addApplicationFont("Orbitron-Bold.ttf")
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
        main_layout.addWidget(right_container, stretch=2)

    # ----------------------------------------------------------------
    def on_serial_data(self, data_list):
        if len(data_list) != 19:
            return

        # Parse data
        roll, pitch, yaw = data_list[0:3]
        accx, accy, accz = data_list[3:6]
        gyrox, gyroy, gyroz = data_list[6:9]
        battery = data_list[9]
        temp = data_list[10]
        lat, lon, alt = data_list[11:14]
        roll_sp, pitch_sp, yaw_sp = data_list[14:17]
        timestamp = data_list[17]
        valid_flag = int(data_list[18])

        # Skip corrupted messages
        if valid_flag != 0:
            return

        # Store for CSV (keep only last 1000)
        self.data_history.append(data_list)
        if len(self.data_history) > 1000:
            self.data_history.pop(0)

        # Update plots
        for axis, current, setpoint in zip(
            ["Roll", "Pitch", "Yaw"],
            [roll, pitch, yaw],
            [roll_sp, pitch_sp, yaw_sp]
        ):
            self.plots[axis].update_plot(current, setpoint)
            self.value_labels[axis]["Angle"].setText(f"Angle: {current:.2f}°")
            self.value_labels[axis]["Setpoint"].setText(f"Setpoint: {setpoint:.2f}°")
            self.value_labels[axis]["Accel"].setText(f"Accel: {data_list[3 + ['Roll','Pitch','Yaw'].index(axis)]:.2f} m/s²")
            self.value_labels[axis]["Gyro"].setText(f"Gyro: {data_list[6 + ['Roll','Pitch','Yaw'].index(axis)]:.2f}°/s")

        # Update cube
        self.cube_widget.set_attitude(roll, pitch, yaw)
        self.cube_widget.set_setpoint(roll_sp, pitch_sp, yaw_sp)

        # Flight info bar
        self.flight_labels["Lat"].setText(f"Lat: {lat:.4f}°")
        self.flight_labels["Long"].setText(f"Long: {lon:.4f}°")
        self.flight_labels["Alt"].setText(f"Alt: {alt:.1f} m")

        # Battery
        self.battery.setValue(battery)

    # ----------------------------------------------------------------
    def save_csv(self):
        """Save last 1000 data points to FlightLog/Odyssey_Log.csv"""
        folder = "FlightLog"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Odyssey_Log.csv")

        headers = [
            "Roll", "Pitch", "Yaw",
            "AccX", "AccY", "AccZ",
            "GyroX", "GyroY", "GyroZ",
            "Battery", "Temperature",
            "Latitude", "Longitude", "Altitude",
            "Roll_Setpoint", "Pitch_Setpoint", "Yaw_Setpoint",
            "Timestamp", "Validity"
        ]

        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(self.data_history)
            print(f"[INFO] Saved {len(self.data_history)} samples to {path}")
        except Exception as e:
            print(f"[ERROR] Saving CSV: {e}")
