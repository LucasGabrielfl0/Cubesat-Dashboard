from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QMainWindow, QComboBox, QFrame,
    QPushButton, QLineEdit, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QFont, QFontDatabase, QColor, QPainter
from PyQt6.QtCore import Qt, QTimer
import os
import csv
from battery_bar import BatteryBar
from plot_widget import AxisPlot
from cube_widget import CubeWidget3D


class UnderlinedLabel(QLabel):
    """Label with cyan underline positioned slightly below text."""
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


class FixedLabel(QLabel):
    """Monospace label with fixed width to prevent layout shifting."""
    def __init__(self, text="", width=120):
        super().__init__(text)
        font = QFont("Consolas", 11)
        self.setFont(font)
        self.setStyleSheet("color: white; background: transparent;")
        self.setFixedWidth(width)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


class MainWindow(QMainWindow):
    def __init__(self, serial_reader=None):
        super().__init__()
        self.setWindowTitle("ATLAS-GroundStation")
        self.resize(1500, 900)
        self.serial_reader = serial_reader
        self.data_history = []
        self.last_validity = 1
        self.initUI()

        if self.serial_reader:
            self.serial_reader.data_received.connect(self.on_serial_data)

    def initUI(self):
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #000000;")
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # === LEFT: GRAPHS ===
        left_layout = QVBoxLayout()
        self.plots = {}
        for axis in ["Roll", "Pitch", "Yaw"]:
            pw = AxisPlot(axis_name=axis)
            left_layout.addWidget(pw)
            self.plots[axis] = pw

        # === RIGHT: Interface ===
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        # === Top: Banner, Port, Battery ===
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

        # === Roll / Pitch / Yaw ===
        attitude_area = QHBoxLayout()
        attitude_area.setSpacing(16)
        self.value_labels = {}

        for axis in ["Roll", "Pitch", "Yaw"]:
            # Outer frame only (first design)
            frame = QFrame()
            frame.setStyleSheet("QFrame { border: 1px solid #003F73; background-color: #000000; border-radius: 6px; }")
            col_layout = QVBoxLayout(frame)
            col_layout.setContentsMargins(8, 8, 8, 8)

            title = UnderlinedLabel(axis)
            col_layout.addWidget(title)

            lbl_sp = FixedLabel("Setpoint: 0.00°")
            lbl_angle = FixedLabel("Angle: 0.00°")
            lbl_acc = FixedLabel("Accel: 0.00 m/s²")
            lbl_gyro = FixedLabel("Gyro: 0.00 °/s")

            for lbl in [lbl_sp, lbl_angle, lbl_acc, lbl_gyro]:
                col_layout.addWidget(lbl)

            col_layout.addStretch()
            attitude_area.addWidget(frame)
            self.value_labels[axis] = {
                "Setpoint": lbl_sp,
                "Angle": lbl_angle,
                "Accel": lbl_acc,
                "Gyro": lbl_gyro
            }

        # === Right-side vertical control panel ===
        control_panel = QFrame()
        control_panel.setStyleSheet("background-color: #111; border: 1px solid #003F73; border-radius: 6px;")
        control_layout = QVBoxLayout(control_panel)
        control_layout.setSpacing(6)

        title = QLabel("Setpoints:")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        control_layout.addWidget(title)

        self.setpoint_inputs = {}
        for axis in ["R", "P", "Y"]:
            row = QHBoxLayout()
            lbl = QLabel(axis)
            lbl.setFont(QFont("Arial", 11))
            lbl.setStyleSheet("color: white;")
            inp = QLineEdit()
            inp.setPlaceholderText("0.0")
            inp.setFixedWidth(72)
            inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inp.setStyleSheet("""
                QLineEdit {
                    background-color: #222;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 3px;
                    padding: 2px;
                }
                QLineEdit:focus { border: 1px solid #007ACC; }
            """)
            row.addWidget(lbl)
            row.addWidget(inp)
            control_layout.addLayout(row)
            self.setpoint_inputs[axis] = inp

        self.send_button = QPushButton("Send")
        self.send_button.setFixedWidth(80)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton:hover { background-color: #005999; }
            QPushButton:pressed { background-color: #003F73; }
        """)
        self.send_button.clicked.connect(self.send_setpoints)
        control_layout.addWidget(self.send_button)
        attitude_area.addWidget(control_panel)
        right_layout.addLayout(attitude_area)

        # === Flight Info Bar ===
        flight_frame = QFrame()
        flight_frame.setFrameShape(QFrame.Shape.Box)
        flight_frame.setStyleSheet("background-color: #111; color: white; padding:5px;")
        flight_layout = QHBoxLayout(flight_frame)
        info_font = QFont("Arial", 11, QFont.Weight.Bold)

        # Comm indicator
        self.comm_label = QLabel("Comm:")
        self.comm_label.setFont(info_font)
        self.comm_label.setStyleSheet("color: white; margin-right: 4px;")
        self.comm_icon = QLabel("📶")
        self.comm_icon.setStyleSheet("color: red; font-size: 16px; margin-right: 4px;")
        flight_layout.addWidget(self.comm_label)
        flight_layout.addWidget(self.comm_icon)

        self.flight_labels = {}
        for label in ["Lat", "Long", "Alt"]:
            lbl = QLabel(f"{label}: 0")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(info_font)
            lbl.setStyleSheet("color: white;")
            flight_layout.addWidget(lbl)
            self.flight_labels[label] = lbl

        flight_layout.addStretch()
        self.log_button = QPushButton("Log Data")
        self.log_button.setFixedHeight(30)
        self.log_button.setFixedWidth(100)
        self.log_button.setStyleSheet("""
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
        self.log_button.clicked.connect(self.save_csv)
        flight_layout.addWidget(self.log_button)
        right_layout.addWidget(flight_frame)

        right_layout.addStretch()

        # === Cube Section ===
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

        # Layout proportions
        main_layout.addLayout(left_layout, stretch=3)
        main_layout.addWidget(right_container, stretch=2)

    # === SERIAL DATA ===
    def on_serial_data(self, data_list):
        if len(data_list) != 19:
            return

        roll, pitch, yaw = data_list[0:3]
        accx, accy, accz = data_list[3:6]
        gyrox, gyroy, gyroz = data_list[6:9]
        battery = data_list[9]
        temp = data_list[10]
        lat, lon, alt = data_list[11:14]
        roll_sp, pitch_sp, yaw_sp = data_list[14:17]
        valid_flag = int(data_list[18])

        self.comm_icon.setStyleSheet(f"color: {'green' if valid_flag == 0 else 'red'}; font-size: 16px; margin-right: 4px;")

        self.data_history.append(data_list)
        if len(self.data_history) > 1000:
            self.data_history.pop(0)

        self.value_labels["Roll"]["Setpoint"].setText(f"Setpoint: {roll_sp:6.2f}°")
        self.value_labels["Pitch"]["Setpoint"].setText(f"Setpoint: {pitch_sp:6.2f}°")
        self.value_labels["Yaw"]["Setpoint"].setText(f"Setpoint: {yaw_sp:6.2f}°")

        self.value_labels["Roll"]["Angle"].setText(f"Angle: {roll:6.2f}°")
        self.value_labels["Pitch"]["Angle"].setText(f"Angle: {pitch:6.2f}°")
        self.value_labels["Yaw"]["Angle"].setText(f"Angle: {yaw:6.2f}°")

        self.value_labels["Roll"]["Accel"].setText(f"Accel: {accx:6.2f} m/s²")
        self.value_labels["Pitch"]["Accel"].setText(f"Accel: {accy:6.2f} m/s²")
        self.value_labels["Yaw"]["Accel"].setText(f"Accel: {accz:6.2f} m/s²")

        self.value_labels["Roll"]["Gyro"].setText(f"Gyro: {gyrox:6.2f} °/s")
        self.value_labels["Pitch"]["Gyro"].setText(f"Gyro: {gyroy:6.2f} °/s")
        self.value_labels["Yaw"]["Gyro"].setText(f"Gyro: {gyroz:6.2f} °/s")

        self.cube_widget.set_attitude(roll, pitch, yaw)
        self.cube_widget.set_setpoint(roll_sp, pitch_sp, yaw_sp)

        self.flight_labels["Lat"].setText(f"Lat: {lat:.4f}°")
        self.flight_labels["Long"].setText(f"Long: {lon:.4f}°")
        self.flight_labels["Alt"].setText(f"Alt: {alt:.1f} m")
        self.battery.setValue(battery)

        self.plots["Roll"].update_plot(roll, roll_sp)
        self.plots["Pitch"].update_plot(pitch, pitch_sp)
        self.plots["Yaw"].update_plot(yaw, yaw_sp)

    # === SEND SETPOINTS ===
    def send_setpoints(self):
        try:
            roll = float(self.setpoint_inputs["R"].text())
            pitch = float(self.setpoint_inputs["P"].text())
            yaw = float(self.setpoint_inputs["Y"].text())
        except ValueError:
            print("[WARN] Invalid setpoint input.")
            return

        cmd = f"[S]: {roll:.2f}, {pitch:.2f}, {yaw:.2f};"
        if self.serial_reader:
            self.serial_reader.send_command(cmd)

        self.send_button.setText("Sent!")
        QTimer.singleShot(1000, self.reset_send_button)

    def reset_send_button(self):
        self.send_button.setText("Send")

    # === SAVE CSV ===
    def save_csv(self):
        folder = "FlightLog"
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "Odyssey_Log.csv")
        headers = [
            "Roll", "Pitch", "Yaw", "AccX", "AccY", "AccZ",
            "GyroX", "GyroY", "GyroZ", "Battery", "Temperature",
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
            self.log_button.setText("Saved!")
            QTimer.singleShot(1000, self.reset_log_button)
        except Exception as e:
            print(f"[ERROR] Saving CSV: {e}")

    def reset_log_button(self):
        self.log_button.setText("Log Data")
