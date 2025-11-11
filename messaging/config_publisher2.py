import asyncio
import json
import random
import time
from nats.aio.client import Client as NATS

# Subjects
CONFIG_INFO_SUBJECT = "sensors.config.info"
CONFIG_FULL_SUBJECT = "sensors.config.full"
SENSOR_DATA_SUBJECT = "sensors.data"
STREAM_NAME = "SENSOR_STREAM"

NUM_GROUPS = 5
SENSORS_PER_GROUP = 60  # 5*60 = 300 sensors

async def main():
    nc = NATS()
    await nc.connect("nats://127.0.0.1:4222")
    js = nc.jetstream()

    # --- Create stream from scratch ---
    subjects = [CONFIG_FULL_SUBJECT, CONFIG_INFO_SUBJECT, SENSOR_DATA_SUBJECT]
    await js.add_stream(name=STREAM_NAME, subjects=subjects)
    print(f"Created stream '{STREAM_NAME}' with subjects: {subjects}")

    # --- Initialize sensor config ---
    full_config = {"version": 1, "groups": []}
    sensor_updates = {}

    for g in range(1, NUM_GROUPS + 1):
        group_name = f"Group {g}"
        sensors = []
        for s in range(1, SENSORS_PER_GROUP + 1):
            sensor_name = f"sensor{g}_{s}"
            sensors.append(sensor_name)
            sensor_updates[sensor_name] = 0
        full_config["groups"].append({"name": group_name, "sensors": sensors})

    version = full_config["version"]

    # --- Publish initial config ---
    await js.publish(CONFIG_FULL_SUBJECT, json.dumps(full_config).encode())
    await js.publish(CONFIG_INFO_SUBJECT, json.dumps({"version": version}).encode())
    print(f"Server started with {NUM_GROUPS * SENSORS_PER_GROUP} sensors, version {version}")

    try:
        while True:
            await asyncio.sleep(0.5)  # every 0.5s

            # --- Randomly update a sensor name ---
            version += 1
            group_idx = random.randint(0, NUM_GROUPS - 1)
            sensor_idx = random.randint(0, SENSORS_PER_GROUP - 1)

            current_name = full_config["groups"][group_idx]["sensors"][sensor_idx]
            base_name = current_name.split('_')[0]  # remove previous _uN suffix

            sensor_updates[base_name] += 1
            new_name = f"{base_name}_u{sensor_updates[base_name]}"
            full_config["groups"][group_idx]["sensors"][sensor_idx] = new_name
            full_config["version"] = version

            # --- Publish config updates every 10th iteration (~5s) ---
            if version % 10 == 0:
                await js.publish(CONFIG_FULL_SUBJECT, json.dumps(full_config).encode())
                await js.publish(CONFIG_INFO_SUBJECT, json.dumps({"version": version}).encode())
                print(f"Published config version {version}")

            # --- Publish sensor data ---
            for group in full_config["groups"]:
                for sensor_name in group["sensors"]:
                    data = {
                        "timestamp": time.time(),
                        "sensor_name": sensor_name,
                        "value": round(random.uniform(0, 100), 2)
                    }
                    await js.publish(SENSOR_DATA_SUBJECT, json.dumps(data).encode())

    except KeyboardInterrupt:
        print("Server stopped.")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())
