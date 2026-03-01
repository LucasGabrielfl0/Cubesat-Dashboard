from PyQt6.QtWidgets import QWidget, QProgressBar, QVBoxLayout
from PyQt6.QtCore import Qt

class BatteryBar(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(80)
        self.bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar.setFormat("BATTERY: %p%")
        self.bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid gray;
                border-radius: 5px;
                text-align: center;
                background-color: #222;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #00c800;
            }
        """)
        layout.addWidget(self.bar)

    def setValue(self, value):
        self.bar.setValue(int(value))
