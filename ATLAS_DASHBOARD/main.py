import sys
from PyQt6.QtWidgets import QApplication
from ui_main import MainWindow
from serial_reader import SerialReader
from PyQt6.QtGui import QIcon

app = QApplication(sys.argv)
app.setWindowIcon(QIcon("Figures/SatteliteIcon.ico"))

serial_reader = SerialReader(port="COM5", baudrate=250000)
serial_reader.start()

window = MainWindow(serial_reader=serial_reader)
window.show()

sys.exit(app.exec())
