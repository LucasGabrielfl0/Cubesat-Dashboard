##=================================== SERIAL READER ==================================##
# Reads Serial Inputs from the ESP32
# Receives:
# AttX, AttY, AttZ | AccX, AccY, AccZ | GyroX, GyroY, GyroZ | Batt, Temp, Time 
#
# Sends:
# AttX, AttY, AttZ
#=================================================================#
from PyQt6.QtCore import QObject, pyqtSignal
import serial
import threading
import struct

# ==== MUST MATCH STM32 ====
INT_TO_ATT  = 0.01
INT_TO_ACC  = 0.001
INT_TO_GYRO = 0.01
INT_TO_BATT = 1.0

PACKET_SIZE = 24  # EXACT size from STM32


class SerialReader(QObject):
    data_received = pyqtSignal(list)

    def __init__(self, port="COM5", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.ser = None

        # Persistent values (remain until updated)
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0

        self.roll_sp = 0.0
        self.pitch_sp = 0.0
        self.yaw_sp = 0.0

    # --------------------------------------------------
    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
            print(f"[INFO] Connected to {self.port} at {self.baudrate} baud")
            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()
        except Exception as e:
            print(f"[ERROR] Could not open serial port: {e}")

    # --------------------------------------------------
    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[INFO] Serial port closed")

    # --------------------------------------------------
    def send_command(self, cmd_tuple):
        """
        Send setpoints as 3x int16 (6 bytes total)
        """
        if not (self.ser and self.ser.is_open):
            return

        try:
            roll_sp, pitch_sp, yaw_sp = cmd_tuple

            self.roll_sp = roll_sp
            self.pitch_sp = pitch_sp
            self.yaw_sp = yaw_sp

            roll_i  = int(roll_sp  / INT_TO_ATT)
            pitch_i = int(pitch_sp / INT_TO_ATT)
            yaw_i   = int(yaw_sp   / INT_TO_ATT)

            packet = struct.pack('<hhh', roll_i, pitch_i, yaw_i)
            self.ser.write(packet)

            print(f"[TX BIN] {roll_i}, {pitch_i}, {yaw_i}")

        except Exception as e:
            print(f"[ERROR] Sending command: {e}")

    # --------------------------------------------------
    def read_loop(self):
        while self.running:
            try:
                packet = self.ser.read(PACKET_SIZE)

                if len(packet) != PACKET_SIZE:
                    continue

                # ----- Optional: Check header nibble -----
                header = packet[0] >> 4
                # sat_id = packet[0] & 0x0F   # if needed

                # ----- Unpack payload -----
                # Skip byte 0 (header)
                data = struct.unpack('<hhhhhhhhhBBB', packet[1:22])

                roll   = data[0] * INT_TO_ATT
                pitch  = data[1] * INT_TO_ATT
                yaw    = data[2] * INT_TO_ATT

                accx   = data[3] * INT_TO_ACC
                accy   = data[4] * INT_TO_ACC
                accz   = data[5] * INT_TO_ACC

                gyrox  = data[6] * INT_TO_GYRO
                gyroy  = data[7] * INT_TO_GYRO
                gyroz  = data[8] * INT_TO_GYRO

                battery   = data[9]  * INT_TO_BATT
                temp      = data[10]
                timestamp = data[11]

                validity = 1  # You can decode from CRC later

                # Build SAME structure your UI expects (19 elements)
                values = [
                    roll, pitch, yaw,
                    accx, accy, accz,
                    gyrox, gyroy, gyroz,
                    battery,
                    temp,
                    self.lat, self.lon, self.alt,
                    self.roll_sp, self.pitch_sp, self.yaw_sp,
                    timestamp,
                    validity
                ]

                self.data_received.emit(values)

            except Exception as e:
                print(f"[ERROR] Reading serial: {e}")
