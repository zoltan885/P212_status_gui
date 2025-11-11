import asyncio
import json
from nats.aio.client import Client as NATS
import random

async def publish_sensors():
    nc = NATS()
    await nc.connect("nats://localhost:4222")

    while True:
        data = {
            "id": "sensor_1",
            "temperature": random.uniform(20, 30),
            "humidity": random.uniform(40, 60)
        }
        await nc.publish("sensors.sensor_1", json.dumps(data).encode())
        await asyncio.sleep(2)

asyncio.run(publish_sensors())
