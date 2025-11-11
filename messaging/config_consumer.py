import asyncio
import json
from functools import partial
from nats.aio.client import Client as NATS
import uuid


CONFIG_INFO_SUBJECT = "sensors.config.info"
CONFIG_FULL_SUBJECT = "sensors.config.full"

local_version = None
full_config_sub = None  # will hold the subscription

async def handle_info(js, msg):
    global local_version
    info = json.loads(msg.data.decode())
    version = info["version"]

    if version != local_version:
        print(f"\nDetected new config version: {version}")
        await fetch_full_config(js)
        local_version = version

async def fetch_full_config(js):
    """
    Fetch the latest full config using a callback subscription.
    Avoid creating a new subscription every time.
    """
    global full_config_sub

    if full_config_sub is None:
        # Create a durable subscription once
        durable_name = f"client-full-{uuid.uuid4()}"
        full_config_sub = await js.subscribe(
            CONFIG_FULL_SUBJECT,
            durable=durable_name,
            cb=handle_full
        )

async def handle_full(msg):
    full_config = json.loads(msg.data.decode())
    print(f"Full config version: {full_config['version']}")
    for group in full_config['groups']:
        print(f"  Group: {group['name']}")
        for sensor in group['sensors']:
            print(f"    Sensor: {sensor}")

async def main():
    nc = NATS()
    await nc.connect("nats://127.0.0.1:4222")
    js = nc.jetstream()

    # Subscribe to info messages
    durable_name = f"client-info-{uuid.uuid4()}"
    await js.subscribe(
        CONFIG_INFO_SUBJECT,
        durable=durable_name,
        cb=partial(handle_info, js)
    )

    print("Client subscribed to config info stream...")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Client stopped.")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())
