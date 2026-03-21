##=================================== SERIAL READER ==================================##
# Reads Serial Inputs from the ESP32
# Receives:
# AttX, AttY, AttZ | AccX, AccY, AccZ | GyroX, GyroY, GyroZ | Batt, Temp, Time
#
# Sends:
# AttX, AttY, AttZ (as 3x int16, little-endian)
#
# Packet Layout (27 bytes):
#   [0:1]   Start bytes  0xAA 0x55
#   [2]     Header       0x01
#   [3]     CubeSat ID
#   [4:21]  IMU data     9x int16 LE  (Roll, Pitch, Yaw, AccX, AccY, AccZ, GyroX, GyroY, GyroZ)
#   [22:24] HK data      3x uint8     (Battery, Temperature, Timestamp)
#   [25:26] CRC-16       uint16 LE    (logged as-is, not validated here)
#====================================================================================#

from PyQt6.QtCore import QObject, pyqtSignal, QThread
import serial
import struct

# ---- Packet constants ----
START_BYTES             = b'\xAA\x55'
PACKET_SIZE             = 27
HEADER_TELEMETRY_PACKET = 0x01

# ---- Scaling factors ----
INT_TO_ATT  = (1 / 16)
INT_TO_ACC  = 0.001
INT_TO_GYRO = (1 / 16)
INT_TO_BATT = (100 / 255)


# ---- Worker thread (keeps serial I/O off the Qt main thread) ----
class _SerialWorker(QThread):
    """
    Runs in its own QThread so that blocking serial reads never stall the GUI
    and pyqtSignal emissions are automatically queued to the main thread.
    """
    data_received = pyqtSignal(list)

    def __init__(self, port: str, baudrate: int):
        super().__init__()
        self.port      = port
        self.baudrate  = baudrate
        self._running  = False
        self.ser       = None

    # --------------------------------------------------
    def open_port(self) -> bool:
        try:
            # timeout=0.05 → brief blocking read; avoids 100% CPU spin
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.05)
            print(f"[INFO] Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"[ERROR] Could not open serial port: {e}")
            return False

    # --------------------------------------------------
    def stop(self):
        self._running = False
        self.wait()                     # join the QThread cleanly
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed")

    # --------------------------------------------------
    def run(self):
        """QThread entry point — called by self.start()."""
        if not self.open_port():
            return

        self._running = True
        buffer = bytearray()

        while self._running:
            try:
                chunk = self.ser.read(max(1, self.ser.in_waiting))
                if not chunk:
                    continue

                buffer.extend(chunk)

                while True:
                    if len(buffer) < PACKET_SIZE:
                        break

                    start_index = buffer.find(START_BYTES)

                    if start_index == -1:
                        buffer.clear()
                        break

                    if start_index > 0:
                        del buffer[:start_index]

                    if len(buffer) < PACKET_SIZE:
                        break

                    packet = buffer[:PACKET_SIZE]

                    # ---- Header check ----
                    if packet[2] != HEADER_TELEMETRY_PACKET:
                        del buffer[:1]
                        continue

                    # ---- Decode payload ----
                    # packet[3]     = CUBESAT_ID  (ignored, validated by CRC on ESP32 side)
                    # packet[4:22]  = 9x int16    (18 bytes)
                    # packet[22:25] = 3x uint8    (3 bytes)
                    # packet[25:27] = CRC uint16  (stored in log as-is)
                    imu = struct.unpack_from('<hhhhhhhhhBBB', packet, 4)
                    crc = struct.unpack_from('<H', packet, 25)[0]

                    roll      = -imu[0] * INT_TO_ATT
                    pitch     = -imu[1] * INT_TO_ATT
                    yaw       = imu[2] * INT_TO_ATT

                    accx      = imu[3] * INT_TO_ACC
                    accy      = imu[4] * INT_TO_ACC
                    accz      = imu[5] * INT_TO_ACC

                    gyrox     = imu[6] * INT_TO_GYRO
                    gyroy     = imu[7] * INT_TO_GYRO
                    gyroz     = imu[8] * INT_TO_GYRO

                    battery   = imu[9]  * INT_TO_BATT
                    temp      = imu[10]
                    timestamp = imu[11]

                    self.data_received.emit([
                        roll, pitch, yaw,
                        accx, accy, accz,
                        gyrox, gyroy, gyroz,
                        battery,
                        temp,
                        0.0, 0.0, 0.0,      # lat, lon, alt  (GPS placeholder)
                        0.0, 0.0, 0.0,      # roll_sp, pitch_sp, yaw_sp (injected by SerialReader)
                        timestamp,
                        1,                  # validity flag
                        crc                 # raw CRC — stored in log only
                    ])

                    del buffer[:PACKET_SIZE]

            except Exception as e:
                print(f"[ERROR] Reading serial: {e}")


# ---- Public API — drop-in replacement for the original SerialReader ----
class SerialReader(QObject):
    """
    Owns the worker QThread and exposes start / stop / reconnect /
    send_command / data_received — same interface as before.
    """
    data_received = pyqtSignal(list)

    def __init__(self, port="COM5", baudrate=115200):
        super().__init__()
        self.port     = port
        self.baudrate = baudrate

        self.roll_sp  = 0.0
        self.pitch_sp = 0.0
        self.yaw_sp   = 0.0

        self._worker = _SerialWorker(port, baudrate)
        self._worker.data_received.connect(self._on_worker_data)

    # --------------------------------------------------
    def start(self):
        self._worker.start()

    # --------------------------------------------------
    def stop(self):
        self._worker.stop()

    # --------------------------------------------------
    def reconnect(self, port: str, baudrate: int):
        """
        Stop the current worker, swap port/baud, and restart.
        Called by the UI when the user changes the dropdowns and clicks Connect.
        """
        print(f"[INFO] Reconnecting → {port} @ {baudrate}")
        self._worker.stop()

        self.port     = port
        self.baudrate = baudrate

        self._worker = _SerialWorker(port, baudrate)
        self._worker.data_received.connect(self._on_worker_data)
        self._worker.start()

    # --------------------------------------------------
    def send_command(self, cmd_tuple):
        """Send setpoints as 3× int16 little-endian (6 bytes)."""
        ser = self._worker.ser
        if not (ser and ser.is_open):
            print("[WARNING] Serial not open — command not sent")
            return
        try:
            roll_sp, pitch_sp, yaw_sp = cmd_tuple

            self.roll_sp  = roll_sp
            self.pitch_sp = pitch_sp
            self.yaw_sp   = yaw_sp

            roll_i  = int(roll_sp  / INT_TO_ATT)
            pitch_i = int(pitch_sp / INT_TO_ATT)
            yaw_i   = int(yaw_sp   / INT_TO_ATT)

            packet = struct.pack('<hhh', roll_i, pitch_i, yaw_i)
            ser.write(packet)
            print(f"[TX] roll={roll_i}  pitch={pitch_i}  yaw={yaw_i}")

        except Exception as e:
            print(f"[ERROR] Sending command: {e}")

    # --------------------------------------------------
    def _on_worker_data(self, values: list):
        """Inject current setpoints into indices 14-16 before re-emitting."""
        values[14] = self.roll_sp
        values[15] = self.pitch_sp
        values[16] = self.yaw_sp
        # self._debug_print(values)   # comment this out to silence debug output
        self.data_received.emit(values)

    # --------------------------------------------------
    def _debug_print(self, v: list):
        """
        Pretty-print every decoded field to the console.
        To disable: comment out the self._debug_print(values) call in _on_worker_data.
        """
        print(
            f"[RX] "
            f"Roll={v[0]:7.2f}°  Pitch={v[1]:7.2f}°  Yaw={v[2]:7.2f}°  | "
            f"Ax={v[3]:7.3f}  Ay={v[4]:7.3f}  Az={v[5]:7.3f} m/s²  | "
            f"Gx={v[6]:7.2f}  Gy={v[7]:7.2f}  Gz={v[8]:7.2f} °/s  | "
            f"Batt={v[9]:5.1f}%  Temp={v[10]}°C  t={v[17]}  CRC=0x{int(v[19]):04X}"
        )