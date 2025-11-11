import os
import asyncio
import json
import random
from prometheus_client import start_http_server, Gauge
from nats.aio.client import Client as NATS

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Define Prometheus metrics
temperature_gauge = Gauge("sensor_temperature", "Temperature °C", ["sensor_id"])
humidity_gauge = Gauge("sensor_humidity", "Humidity %", ["sensor_id"])

async def main():
    nc = NATS()
    await nc.connect(NATS_URL)

    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        sensor_id = data["id"]
        temperature_gauge.labels(sensor_id=sensor_id).set(data["temperature"])
        humidity_gauge.labels(sensor_id=sensor_id).set(data["humidity"])

    await nc.subscribe("sensors.*", cb=message_handler)

    print("Sensor exporter listening for NATS messages...")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    start_http_server(8000)
    asyncio.run(main())
