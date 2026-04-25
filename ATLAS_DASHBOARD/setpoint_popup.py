from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QPushButton
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer


class SetpointPopup(QDialog):
    """
    Compact floating window for roll, pitch, and yaw setpoints.
    Leave any field blank to skip that axis — only filled axes are sent.
    """
    def __init__(self, serial_reader=None):
        super().__init__()
        self.serial_reader = serial_reader
        self.setWindowTitle("Setpoints")
        self.setStyleSheet("background-color: #111; color: white;")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Window)
        self.setFixedSize(300, 150)          # compact — no wasted space

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # axis key → (prefix label, range hint)
        axis_config = [
            ("R", "Roll  (−180…180)°:"),
            ("P", "Pitch  (−90…90)°:"),
            ("Y", "Yaw     (0…360)°:"),
        ]

        self.inputs = {}
        field_style = """
            QLineEdit {
                background-color: #1a1a2e;
                color: white;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 2px 4px;
            }
            QLineEdit:focus { border: 1px solid #007ACC; }
        """
        lbl_font  = QFont("Consolas", 10)
        inp_font  = QFont("Consolas", 10)

        for axis, label_text in axis_config:
            row = QHBoxLayout()
            row.setSpacing(6)

            lbl = QLabel(label_text)
            lbl.setFont(lbl_font)
            lbl.setStyleSheet("color: #B0B0B0;")
            lbl.setFixedWidth(150)

            inp = QLineEdit()
            inp.setFont(inp_font)
            inp.setPlaceholderText("—")
            inp.setFixedWidth(80)
            inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            inp.setStyleSheet(field_style)

            row.addWidget(lbl)
            row.addWidget(inp)
            layout.addLayout(row)
            self.inputs[axis] = inp

        self.send_button = QPushButton("Send")
        self.send_button.setFixedHeight(26)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #007ACC;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover   { background-color: #005999; }
            QPushButton:pressed { background-color: #003F73; }
        """)
        self.send_button.clicked.connect(self.send_setpoints)
        layout.addWidget(self.send_button)

    # --------------------------------------------------
    def send_setpoints(self):
        """
        Only send axes whose fields are non-empty.
        Passes a dict to SerialReader.send_command() so the ESP32 only
        updates the axes explicitly set.
        """
        LIMITS = {
            'R': (-180.0, 180.0),
            'P': ( -90.0,  90.0),
            'Y': (   0.0, 360.0),
        }

        cmd_dict = {}
        error    = False

        for axis, inp in self.inputs.items():
            text = inp.text().strip()
            if not text:
                continue                    # blank → skip this axis
            try:
                val = float(text)
            except ValueError:
                error = True
                inp.setStyleSheet(inp.styleSheet() + "border: 1px solid #CC3300;")
                continue

            lo, hi = LIMITS[axis]
            val = max(lo, min(hi, val))
            inp.setText(f"{val:.2f}")       # show clamped value back
            cmd_dict[axis] = val

        if error:
            self.send_button.setText("Bad input!")
            QTimer.singleShot(1500, lambda: self.send_button.setText("Send"))
            return

        if not cmd_dict:
            self.send_button.setText("Nothing to send")
            QTimer.singleShot(1200, lambda: self.send_button.setText("Send"))
            return

        if self.serial_reader:
            self.serial_reader.send_command(cmd_dict)

        self.send_button.setText("Sent!")
        QTimer.singleShot(1000, lambda: self.send_button.setText("Send"))