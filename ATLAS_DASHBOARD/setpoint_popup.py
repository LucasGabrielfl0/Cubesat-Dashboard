from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QPushButton
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer


class SetpointPopup(QDialog):
    """
    Floating window for roll, pitch, and yaw setpoints.
    """
    def __init__(self, serial_reader=None):
        super().__init__()
        self.serial_reader = serial_reader
        self.setWindowTitle("Setpoints")
        self.setStyleSheet("background-color: #111; color: white;")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self.setMinimumSize(400, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Setpoints")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.inputs = {}
        for axis, label_text in zip(
            ["R", "P", "Y"],
            ["Roll Setpoint (°):", "Pitch Setpoint (°):", "Yaw Setpoint (°):"]
        ):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Arial", 11))
            lbl.setStyleSheet("color: white;")

            inp = QLineEdit()
            inp.setPlaceholderText("0.0")
            inp.setFixedWidth(120)
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
            layout.addLayout(row)
            self.inputs[axis] = inp

        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 5px 5px;
            }
            QPushButton:hover { background-color: #005999; }
            QPushButton:pressed { background-color: #003F73; }
        """)
        self.send_button.clicked.connect(self.send_setpoints)
        layout.addWidget(self.send_button)

    def send_setpoints(self):
        """
        Collects input values and sends them via serial (if connected).
        """
        try:
            roll = float(self.inputs["R"].text())
            pitch = float(self.inputs["P"].text())
            yaw = float(self.inputs["Y"].text())
        except ValueError:
            print("[WARN] Invalid setpoint input.")
            return

        cmd = f"[S]: {roll:.2f}, {pitch:.2f}, {yaw:.2f};"
        if self.serial_reader:
            self.serial_reader.send_command((roll, pitch, yaw))

        self.send_button.setText("Sent!")
        QTimer.singleShot(1000, lambda: self.send_button.setText("Send"))
