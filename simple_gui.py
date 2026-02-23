import sys
import time
import json
import asyncio

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QTimer

import asyncio
import nkeys
import base64
import time
import json
import gzip
from nats.aio.client import Client as NATS
from load_credits import parse_creds

VERBOSE = True  # Set to True for verbose output
CRED_PATH = "/home/hegedues/prog/nats/NGS-Default-CLI.creds"

# ---------------- Tango colors ----------------
_TangoStateColors = {
    'ON': '#6beda5',
    'OFF': '#f4f7f2',
    'MOVING': '#427ef5',
    'STANDBY': '#f5f253',
    'FAULT': '#cc2b2b',
    'INIT': '#daa06d',
    'ALARM': '#eb962f',
    'DISABLE': '#f037fa',
    'UNKNOWN': '#808080',
    None: '#808080'
}

# ---------------- Signal bridge ----------------
class NatsSignalBridge(QObject):
    message_received = pyqtSignal(dict)

# ---------------- Telemetry model ----------------
class TelemetryModel:
    def __init__(self):
        self.data = {}

    def update(self, partial):
        for key, sensor in partial.items():
            if key not in self.data:
                self.data[key] = sensor
            else:
                self.data[key].update(sensor)

# ---------------- Main window ----------------
class MainWindow(QMainWindow):
    def __init__(self, bridge):
        super().__init__()
        self.setWindowTitle("NATS Telemetry Viewer")
        self.model = TelemetryModel()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Value", "State", "Timestamp"]
        )

        layout = QVBoxLayout()
        layout.addWidget(self.table)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        bridge.message_received.connect(self.apply_update)

    def apply_update(self, message):
        self.model.update(message)
        self.refresh_table()

    def refresh_table(self):
        sensors = list(self.model.data.values())
        self.table.setRowCount(len(sensors))

        for row, sensor in enumerate(sensors):
            state = sensor.get("state")
            bg = QColor(_TangoStateColors.get(state, "#ffffff"))

            items = [
                QTableWidgetItem(sensor.get("name", "")),
                QTableWidgetItem(str(sensor.get("value"))),
                QTableWidgetItem(str(state)),
                QTableWidgetItem(
                    time.strftime(
                        "%H:%M:%S",
                        time.localtime(sensor.get("timestamp", 0))
                    )
                )
            ]

            for col, item in enumerate(items):
                item.setBackground(bg)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)

# ---------------- NATS client class ----------------
class NatsClient:
    def __init__(self, bridge):
        self.bridge = bridge
        self.jwt, seed = parse_creds(CRED_PATH)
        self.kp = nkeys.from_seed(seed.encode())
        self.nc = NATS()

    async def start(self):
        await self.nc.connect(
        servers=["tls://connect.ngs.global:4222"],
        user_jwt_cb=lambda: self.jwt.encode("utf-8"),
        signature_cb=lambda nonce: base64.b64encode(self.kp.sign(nonce.encode())),
        name="jwt-subscriber",
        )

        await self.nc.subscribe("sensors.updates", cb=self._handler)
        print("Subscribed to telemetry")

    def is_gzipped(self, data: bytes) -> bool:
        return data[:2] == b'\x1f\x8b'

    def decode_message(self, data: bytes) -> dict:
        if self.is_gzipped(data):
            decompressed = gzip.decompress(data)
        else:
            decompressed = data
        return json.loads(decompressed.decode("utf-8"))

    async def _handler(self, msg):
        update = self.decode_message(msg.data)
        try:
            self.bridge.message_received.emit(update)
            if VERBOSE:
                print(f"Update: {update}")

        except Exception as e:
            print("Message error:", e)

# ---------------- Main entry ----------------
def main():
    app = QApplication(sys.argv)

    bridge = NatsSignalBridge()
    window = MainWindow(bridge)
    window.resize(800, 450)
    window.show()

    nats_client = NatsClient(bridge)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(nats_client.start())

    # integrate asyncio loop with Qt
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(50)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()