import asyncio
import random
import time
from copy import deepcopy
from collections import deque
import sys

import pyqtgraph as pg
from PyQt5 import QtWidgets
import qasync  # asyncio + Qt integration

NOISE = 0.05  # ±5% noise
JUMP_TIME = 5  # seconds for jump

SENSOR_CONFIG = {}
for i in range(1, 1001):
    SENSOR_CONFIG[f"sensor{i}"] = {
        "poll_time": round(random.uniform(0.2, 0.6), 2),         # 0.2 to 0.6 seconds
        "noise": random.choice([True, False]),
        "value": round(random.uniform(1e-6, 20.0), 6),           # 1e-6 to 20.0
        "jump": random.choice([True, False]),
        "jump_step": round(random.uniform(0.01, 2.0), 3)         # 0.01 to 2.0
    }

# SENSOR_CONFIG = {
#         "sensor1": {"poll_time": 0.3, "noise": True, "value": 1e-5, "jump": False, "jump_step": 1e-6},
#         "sensor2": {"poll_time": 0.5, "noise": False, "value": 1.0, "jump": True, "jump_step": 0.1},
#         "sensor3": {"poll_time": 0.4, "noise": True, "value": 5.0, "jump": True, "jump_step": 0.5},
#         "sensor4": {"poll_time": 0.3, "noise": False, "value": 10.0, "jump": False, "jump_step": 0.2},
#         "sensor5": {"poll_time": 0.25, "noise": True, "value": 2.5, "jump": True, "jump_step": 1},
#     }


class AsyncSensorSimulator:
    def __init__(self, sensor_config: dict, output_queue: asyncio.Queue = None):
        """
        sensor_config: dictionary like:
        {
            "sensor1": {
                "poll_time": 0.3,
                "noise": True,
                "value": 1e-5,
                "jump": False,
                "jump_step": 1e-6
            },
            ...
        }
        """
        self.sensor_config = deepcopy(sensor_config)
        self.queue = output_queue
        self.tasks = []
        self._stop_event = asyncio.Event()
        self.IDs = [0]

    async def start(self):
        """Start simulation tasks for all sensors."""
        for name, cfg in self.sensor_config.items():
            self.IDs.append(self.IDs[-1] + 1)

            self.tasks.append(
                asyncio.create_task(self._simulate_sensor(name, cfg, ID=self.IDs[-1]))
            )

    async def stop(self):
        """Stop all sensor simulation tasks."""
        self._stop_event.set()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def _simulate_sensor(self, name, cfg, ID=0):
        value = cfg["value"]
        poll_time = cfg["poll_time"]
        noise = cfg.get("noise", False)
        jump = cfg.get("jump", False)
        jump_step = cfg.get("jump_step", 0)
        last_jump_time = time.time()

        while not self._stop_event.is_set():
            # Jitter: vary poll time by ±10% of poll_time
            jitter = poll_time * 0.1
            await asyncio.sleep(poll_time + random.uniform(-jitter, jitter))

            # Handle jump every 30 sec
            now = time.time()
            if jump and (now - last_jump_time >= JUMP_TIME):
                value += random.uniform(-jump_step, jump_step)
                last_jump_time = now

            # Add noise if enabled (±5% of current value)
            current_value = value
            if noise:
                current_value *= 1 + random.uniform(-NOISE, NOISE)

            # Put into queue
            # await self.queue.put({
            #     name: {
            #         "ID": ID,
            #         "name": name,
            #         "timestamp": now,
            #         "value": current_value,
            #         "state": "ON"
            #     }
            # })
            await self.queue.put({
                "ID": ID,
                "name": name,
                "timestamp": now,
                "value": current_value,
                "state": "OFF"
            })

class MultiSensorPlotter(QtWidgets.QMainWindow):
    def __init__(self, queue, sensor_names, max_points=5000):
        super().__init__()
        self.queue = queue
        self.max_points = max_points
        self.sensor_names = sensor_names

        self.setWindowTitle("Multi-Sensor Viewer")
        self.resize(1000, 800)

        # Central widget
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        self.setCentralWidget(central)

        self.data_buffers = {name: deque(maxlen=max_points) for name in sensor_names}
        self.plots = {}
        self.curves = {}

        # Create first plot as "master"
        self.master_plot = pg.PlotWidget()
        self.master_plot.setTitle(sensor_names[0])
        self.master_plot.showGrid(x=True, y=True)
        self.master_plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        master_curve = self.master_plot.plot([], [], pen='y')

        layout.addWidget(self.master_plot)
        self.plots[sensor_names[0]] = self.master_plot
        self.curves[sensor_names[0]] = master_curve

        # Create linked plots for remaining sensors
        for name in sensor_names[1:]:
            plot_widget = pg.PlotWidget()
            plot_widget.setTitle(name)
            plot_widget.showGrid(x=True, y=True)
            plot_widget.enableAutoRange(axis=pg.ViewBox.YAxis)

            # Link the X-axis to the master plot
            plot_widget.setXLink(self.master_plot)

            curve = plot_widget.plot([], [], pen='y')
            layout.addWidget(plot_widget)

            self.plots[name] = plot_widget
            self.curves[name] = curve

    async def run(self):
        """Consume queue and update all subplots."""
        while True:
            msg = await self.queue.get()

            for sensor_name, data in msg.items():
                t = data["timestamp"]
                v = data["value"]

                buf = self.data_buffers[sensor_name]
                buf.append((t, v))

                times, values = zip(*buf)
                t0 = times[0]  # normalize to zero
                self.curves[sensor_name].setData(
                    [ti - t0 for ti in times], values
                )


# Example usage
async def main_simple():
    config = SENSOR_CONFIG

    # Create an output queue for sensor data
    output_queue = asyncio.Queue()

    sim = AsyncSensorSimulator(config, output_queue)
    await sim.start()

    while True:
        try:
            measurement = await output_queue.get()
            print(measurement)
        except asyncio.CancelledError:
            break

    await sim.stop()

async def main_plot():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    config = SENSOR_CONFIG

    # Create an output queue for sensor data
    output_queue = asyncio.Queue()

    sim = AsyncSensorSimulator(config, output_queue)
    plotter = MultiSensorPlotter(output_queue, sensor_names=list(config.keys()))
    plotter.show()

    async def startup():
        await sim.start()
        await plotter.run()

    with loop:
        loop.create_task(startup())
        loop.run_forever()

if __name__ == "__main__":
    asyncio.run(main_simple())