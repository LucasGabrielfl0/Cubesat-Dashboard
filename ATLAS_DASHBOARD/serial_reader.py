##=================================== SERIAL READER ==================================##
# Reads Serial Inputs from the ESP32 Ground Station
#
# Receives (Telemetry Packet, 25 bytes) [Every ~100ms]:
#   [0]         0xAA            START_BYTE1
#   [1]         0x55            START_BYTE2
#   [2]         0x01            HEADER_TELEMETRY_PACKET
#   [3]         0x01            ODYSSEY_ID
#   [4:21]      ATT+ACC+GYRO    9x int16 LE  (Roll, Pitch, Yaw, AccX-Z, GyroX-Z)
#   [22]        MsgCounter      uint8
#   [23:24]     CRC-16          uint16 LE    (CRC-CCITT-16)
#
# Receives (House Keeping Packet, 22 bytes) [Every ~2s]:
#   [0]         0xAA            START_BYTE1
#   [1]         0x55            START_BYTE2
#   [2]         0x02            HEADER_HOUSE_KEEPING_PACKET
#   [3]         0x01            ODYSSEY_ID
#   [4:9]       ATT Setpoints   3x int16 LE  (Roll_SP, Pitch_SP, Yaw_SP)  [×0.01 deg]
#   [10:15]     GPS             3x int16 LE  (Lat, Lon, Alt)
#   [16:17]     Battery%        int16 LE     [×0.01 → %]
#   [18]        Temperature     uint8        [raw − 50 → °C]
#   [19]        Mode            uint8
#   [20:21]     CRC-16          uint16 LE
#
# Sends (Control Packet — plain ASCII, newline-terminated):
#   "r{roll};p{pitch};y{yaw};\n"
#   e.g. "r45.00;p-10.00;y180.00;\n"
#   Matches what parseSerialCommand() on the ESP32 expects.
#====================================================================================#

from PyQt6.QtCore import QObject, pyqtSignal, QThread
import serial
import struct

# ---- Packet constants ----
START_BYTES                 = b'\xAA\x55'
HEADER_TELEMETRY_PACKET     = 0x01
HEADER_HOUSE_KEEPING_PACKET = 0x02
TELEMETRY_PACKET_SIZE       = 25
HOUSEKEEPING_PACKET_SIZE    = 24

# ---- Scaling factors (RX — incoming telemetry) ----
INT_TO_ATT  = (1.0 / 16.0)     # BNO055 Euler: 1/16 deg per LSB
INT_TO_ACC  = (1.0 / 1000.0)   # Accelerometer: sent in mg → divide by 1000 → g
INT_TO_GYRO = (1.0 / 16.0)     # Gyroscope: 1/16 °/s per LSB
INT_TO_BATT = 0.01              # Battery int16 → %
INT_TO_HK_ATT = 0.01           # HK setpoints (ATT_TO_INT = 100 on ESP32 side)

# ---- Setpoint clamp limits ----
ROLL_MIN,  ROLL_MAX  = -180.0, 180.0
PITCH_MIN, PITCH_MAX =  -90.0,  90.0
YAW_MIN,   YAW_MAX   =    0.0, 360.0


# ---- Worker thread ----
class _SerialWorker(QThread):
    """Blocking serial reads in a dedicated thread; signals auto-queue to main thread."""
    telemetry_received    = pyqtSignal(list)
    housekeeping_received = pyqtSignal(list)

    def __init__(self, port: str, baudrate: int):
        super().__init__()
        self.port     = port
        self.baudrate = baudrate
        self._running = False
        self.ser      = None

    def open_port(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.05)
            print(f"[INFO] Connected to {self.port} at {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"[ERROR] Could not open serial port: {e}")
            return False

    def stop(self):
        self._running = False
        self.wait()
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed")

    def run(self):
        if not self.open_port():
            return

        self._running = True
        buffer = bytearray()

        PACKET_SIZES = {
            HEADER_TELEMETRY_PACKET:     TELEMETRY_PACKET_SIZE,
            HEADER_HOUSE_KEEPING_PACKET: HOUSEKEEPING_PACKET_SIZE,
        }

        while self._running:
            try:
                chunk = self.ser.read(max(1, self.ser.in_waiting))
                if not chunk:
                    continue

                buffer.extend(chunk)

                while True:
                    if len(buffer) < 3:
                        break

                    start_index = buffer.find(START_BYTES)
                    if start_index == -1:
                        buffer.clear()
                        break
                    if start_index > 0:
                        del buffer[:start_index]
                    if len(buffer) < 3:
                        break

                    header      = buffer[2]
                    packet_size = PACKET_SIZES.get(header)

                    if packet_size is None:
                        del buffer[:1]   # unknown header, skip one byte
                        continue

                    if len(buffer) < packet_size:
                        break            # wait for more bytes

                    packet = bytes(buffer[:packet_size])

                    if header == HEADER_TELEMETRY_PACKET:
                        self._decode_telemetry(packet)
                    elif header == HEADER_HOUSE_KEEPING_PACKET:
                        self._decode_housekeeping(packet)

                    del buffer[:packet_size]

            except Exception as e:
                print(f"[ERROR] Reading serial: {e}")

    # --------------------------------------------------
    def _decode_telemetry(self, packet: bytes):
        """
        [4:21]  9× int16 LE  → Roll, Pitch, Yaw, AccX, AccY, AccZ, GyroX, GyroY, GyroZ
        [22]    uint8        → MsgCounter
        [23:24] uint16 LE   → CRC-16
        """
        imu     = struct.unpack_from('<hhhhhhhhh', packet, 4)   # 9× int16
        counter = packet[22]
        crc     = struct.unpack_from('<H', packet, 23)[0]

        self.telemetry_received.emit([
            imu[0] * INT_TO_ATT,    # roll     [0]
            imu[1] * INT_TO_ATT,    # pitch    [1]
            imu[2] * INT_TO_ATT,    # yaw      [2]
            imu[3] * INT_TO_ACC,    # accx     [3]
            imu[4] * INT_TO_ACC,    # accy     [4]
            imu[5] * INT_TO_ACC,    # accz     [5]
            imu[6] * INT_TO_GYRO,   # gyrox    [6]
            imu[7] * INT_TO_GYRO,   # gyroy    [7]
            imu[8] * INT_TO_GYRO,   # gyroz    [8]
            counter,                # counter  [9]
            crc,                    # crc      [10]
        ])

    # --------------------------------------------------
    def _decode_housekeeping(self, packet: bytes):
        """
        HK packet (24 bytes) layout:
          [4:9]   3× int16 LE  → Roll_SP, Pitch_SP, Yaw_SP  (×0.01 → °)
          [10:11] int16 LE     → Battery  (×0.01 → V)
          [12]    uint8        → Temperature (raw ÷ 2 → °C, range 0–127.5)
          [13]    uint8        → Status (0–255)
          [14:17] int32 LE     → Latitude  (scale TBD)
          [18:21] int32 LE     → Longitude (scale TBD)
          [22:23] uint16 LE    → CRC-16
        """
        sp_roll_i, sp_pitch_i, sp_yaw_i, batt_i = \
            struct.unpack_from('<hhhh', packet, 4)      # 4× int16
        temp_raw = packet[12]                           # uint8
        status   = packet[13]                           # uint8
        lat_i    = struct.unpack_from('<i', packet, 14)[0]  # int32 (scale TBD)
        lon_i    = struct.unpack_from('<i', packet, 18)[0]  # int32 (scale TBD)
        crc      = struct.unpack_from('<H', packet, 22)[0]

        self.housekeeping_received.emit([
            sp_roll_i * INT_TO_HK_ATT,  # roll_sp   [0]
            sp_pitch_i * INT_TO_HK_ATT, # pitch_sp  [1]
            sp_yaw_i * INT_TO_HK_ATT,   # yaw_sp    [2]
            float(lat_i),               # lat       [3]  (scale TBD)
            float(lon_i),               # lon       [4]  (scale TBD)
            batt_i * INT_TO_BATT,       # battery   [5]
            temp_raw / 2.0,             # temp °C   [6]
            status,                     # status    [7]
            crc,                        # crc       [8]
        ])


# ---- Public API ----
class SerialReader(QObject):
    """
    Owns the worker QThread.

    Merges telemetry + housekeeping into the unified 20-element data_received
    signal so ui_main.py needs no changes:

      [0:3]   roll, pitch, yaw
      [3:6]   accx, accy, accz
      [6:9]   gyrox, gyroy, gyroz
      [9]     battery      ← updated by HK packet (0.0 until first HK arrives)
      [10]    temp         ← same
      [11:14] lat, lon, alt
      [14:17] roll_sp, pitch_sp, yaw_sp  ← from last send_command()
      [17]    msg_counter
      [18]    validity flag  (always 1)
      [19]    crc
    """
    data_received = pyqtSignal(list)

    def __init__(self, port="COM5", baudrate=115200, debug=False, debug_hk=False):
        super().__init__()
        self.port      = port
        self.baudrate  = baudrate
        self.debug     = debug
        self.debug_hk  = debug_hk

        # Cached from last HK packet
        self._battery  = 0.0
        self._temp     = 0.0
        self._lat      = 0.0
        self._lon      = 0.0
        self._status   = 0

        # Last setpoints sent by the user
        self.roll_sp   = 0.0
        self.pitch_sp  = 0.0
        self.yaw_sp    = 0.0

        self._worker = _SerialWorker(port, baudrate)
        self._worker.telemetry_received.connect(self._on_telemetry)
        self._worker.housekeeping_received.connect(self._on_housekeeping)

    def start(self):
        self._worker.start()

    def stop(self):
        self._worker.stop()

    def reconnect(self, port: str, baudrate: int):
        print(f"[INFO] Reconnecting → {port} @ {baudrate}")
        self._worker.stop()
        self.port     = port
        self.baudrate = baudrate
        self._worker  = _SerialWorker(port, baudrate)
        self._worker.telemetry_received.connect(self._on_telemetry)
        self._worker.housekeeping_received.connect(self._on_housekeeping)
        self._worker.start()

    # --------------------------------------------------
    def send_command(self, cmd_dict: dict):
        """
        Send a partial or full ASCII setpoint command to the ESP32.

        cmd_dict keys (all optional):
          'R' -> roll  float  (-180 ... 180)
          'P' -> pitch float  (-90  ...  90)
          'Y' -> yaw   float  (0    ... 360)

        Only axes present in cmd_dict are sent, so the ESP32 only updates
        those axes. Matches parseSerialCommand() in Dashboard.cpp.
        """
        ser = self._worker.ser
        if not (ser and ser.is_open):
            print("[WARN] Serial not open — command not sent")
            return
        if not cmd_dict:
            print("[WARN] send_command called with empty dict — nothing to send")
            return
        try:
            parts = []

            if 'R' in cmd_dict:
                val = max(ROLL_MIN,  min(ROLL_MAX,  float(cmd_dict['R'])))
                self.roll_sp = val
                parts.append(f"r{val:.1f};")

            if 'P' in cmd_dict:
                val = max(PITCH_MIN, min(PITCH_MAX, float(cmd_dict['P'])))
                self.pitch_sp = val
                parts.append(f"p{val:.1f};")

            if 'Y' in cmd_dict:
                val = max(YAW_MIN,   min(YAW_MAX,   float(cmd_dict['Y'])))
                self.yaw_sp = val
                parts.append(f"y{val:.1f};")

            cmd = "".join(parts) + "\n"
            ser.write(cmd.encode('ascii'))
            print(cmd.strip())

        except Exception as e:
            print(f"[ERROR] Sending command: {e}")

    # --------------------------------------------------
    def _on_telemetry(self, values: list):
        unified = [
            values[0], values[1], values[2],            # roll, pitch, yaw      [0:3]
            values[3], values[4], values[5],            # accx, accy, accz      [3:6]
            values[6], values[7], values[8],            # gyrox, gyroy, gyroz   [6:9]
            self._battery,                              # battery               [9]
            self._temp,                                 # temp                  [10]
            self._lat, self._lon, self._status,         # lat, lon, status      [11:14]
            self.roll_sp, self.pitch_sp, self.yaw_sp,   # setpoints             [14:17]
            values[9],                                  # msg_counter           [17]
            1,                                          # validity              [18]
            values[10],                                 # crc                   [19]
        ]
        if self.debug:
            self._debug_print(unified)
        self.data_received.emit(unified)

    # --------------------------------------------------
    def _on_housekeeping(self, values: list):
        self._lat      = values[3]
        self._lon      = values[4]
        self._battery  = values[5]
        self._temp     = values[6]
        self._status   = values[7]
        # Update displayed setpoints with cubesat feedback
        self.roll_sp   = values[0]
        self.pitch_sp  = values[1]
        self.yaw_sp    = values[2]
        if self.debug_hk:
            print(f"[HK] Batt={self._battery:.2f}V  Temp={self._temp:.1f}°C  "
                  f"Status={self._status}  Lat={self._lat}  Lon={self._lon}  "
                  f"Roll_SP={self.roll_sp:.2f}  Pitch_SP={self.pitch_sp:.2f}  Yaw_SP={self.yaw_sp:.2f}")

    # --------------------------------------------------
    def _debug_print(self, v: list):
        print(
            f"[RX] "
            f"Roll={v[0]:7.2f}°  Pitch={v[1]:7.2f}°  Yaw={v[2]:7.2f}°  | "
            f"Ax={v[3]:7.3f}  Ay={v[4]:7.3f}  Az={v[5]:7.3f} g  | "
            f"Gx={v[6]:7.2f}  Gy={v[7]:7.2f}  Gz={v[8]:7.2f} °/s  | "
            f"Batt={v[9]:5.1f}%  Temp={v[10]}°C  cnt={v[17]}  CRC=0x{int(v[19]):04X}"
        )