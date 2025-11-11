import asyncio
import json
from nats.aio.client import Client as NATS

CONFIG_INFO_SUBJECT = "sensors.config.info"
CONFIG_FULL_SUBJECT = "sensors.config.full"
SENSOR_DATA_SUBJECT = "sensors.data"

async def main():
    nc = NATS()
    await nc.connect("nats://127.0.0.1:4222")
    js = nc.jetstream()

    # Latest config storage
    latest_config = {}
    latest_version = 0

    # --- Callback for config full updates ---
    async def config_full_handler(msg):
        nonlocal latest_config, latest_version
        data = json.loads(msg.data.decode())
        latest_config = data
        latest_version = data.get("version", latest_version)
        print(f"\n=== CONFIG FULL UPDATED (version {latest_version}) ===")
        for group in latest_config.get("groups", []):
            print(f"Group: {group['name']}, Sensors: {group['sensors']}")

    # --- Callback for config info (version only) ---
    async def config_info_handler(msg):
        data = json.loads(msg.data.decode())
        version = data.get("version", 0)
        if version > latest_version:
            print(f"\nConfig version updated to {version}, consider fetching full config")

    # --- Callback for sensor data ---
    async def sensor_data_handler(msg):
        data = json.loads(msg.data.decode())
        print(f"Sensor: {data['sensor_name']}, Value: {data['value']:.2f}, Timestamp: {data['timestamp']}")

    # --- Subscribe to JetStream subjects ---
    await js.subscribe(CONFIG_FULL_SUBJECT, cb=config_full_handler)
    await js.subscribe(CONFIG_INFO_SUBJECT, cb=config_info_handler)
    await js.subscribe(SENSOR_DATA_SUBJECT, cb=sensor_data_handler)

    print("Client started. Listening for sensor data and config updates...\n")

    try:
        while True:
            await asyncio.sleep(1)  # keep the loop alive
    except KeyboardInterrupt:
        print("Client stopped.")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())
