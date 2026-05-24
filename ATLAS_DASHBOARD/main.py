##=================================== DASHBOARD MAIN ==================================##
#
#====================================================================================#

import sys, os
from PyQt6.QtWidgets import QApplication
from ui_main import MainWindow
from serial_reader import SerialReader
from PyQt6.QtGui import QIcon

def resource_path(relative_path):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

app = QApplication(sys.argv)
app.setWindowIcon(QIcon(resource_path("Figures/SatteliteIcon.ico")))

# DEBUG: print decoded telemetry packets to console
DEBUG_TELEMETRY = False
# DEBUG: print decoded housekeeping packets to console
DEBUG_HK        = False

# Serial Setup
serial_reader = SerialReader(
    port      = "COM6",
    baudrate  = 250000,
    debug     = DEBUG_TELEMETRY,
    debug_hk  = DEBUG_HK,
)
serial_reader.start()

window = MainWindow(serial_reader=serial_reader)
window.show()

sys.exit(app.exec())