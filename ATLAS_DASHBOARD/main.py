##=================================== DASHBOARD MAIN ==================================##
#
#====================================================================================#

import sys
from PyQt6.QtWidgets import QApplication
from ui_main import MainWindow
from serial_reader import SerialReader
from PyQt6.QtGui import QIcon

app = QApplication(sys.argv)
app.setWindowIcon(QIcon("Figures/SatteliteIcon.ico"))

# DEBUG: print decoded telemetry packets to console
DEBUG_TELEMETRY = False
# DEBUG: print decoded housekeeping packets to console
DEBUG_HK        = False
# Show face markers on 3D cube (LEDs, circles, antenna square)
SHOW_FACE_MARKERS = False

# Serial Setup
serial_reader = SerialReader(
    port      = "COM8",
    baudrate  = 250000,
    debug     = DEBUG_TELEMETRY,
    debug_hk  = DEBUG_HK,
)
serial_reader.start()

window = MainWindow(serial_reader=serial_reader, show_face_markers=SHOW_FACE_MARKERS)
window.show()

sys.exit(app.exec())