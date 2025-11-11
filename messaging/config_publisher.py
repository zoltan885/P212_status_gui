import asyncio
import json
import random
from nats.aio.client import Client as NATS

CONFIG_INFO_SUBJECT = "sensors.config.info"
CONFIG_FULL_SUBJECT = "sensors.config.full"

async def main():
    nc = NATS()
    await nc.connect("nats://127.0.0.1:4222")
    js = nc.jetstream()

    # Initial configuration
    full_config = {
        "version": 1,
        "groups": [
            {"name": "Group A", "sensors": ["sensor1", "sensor2"]},
            {"name": "Group B", "sensors": ["sensor3"]}
        ]
    }

    # Track update counts per base sensor name
    sensor_updates = {s: 0 for g in full_config["groups"] for s in g["sensors"]}

    # Publish initial full config
    await js.publish(CONFIG_FULL_SUBJECT, json.dumps(full_config).encode())
    await js.publish(CONFIG_INFO_SUBJECT, json.dumps({"version": full_config["version"]}).encode())
    print(f"Server started with version {full_config['version']}")

    version = full_config["version"]
    try:
        while True:
            await asyncio.sleep(5)  # every 5 seconds, simulate update
            version += 1

            # Randomly pick a group and a sensor index
            group_idx = random.randint(0, len(full_config["groups"]) - 1)
            sensor_idx = random.randint(0, len(full_config["groups"][group_idx]["sensors"]) - 1)

            # Extract the **base name** (strip any previous _uN suffix)
            current_name = full_config["groups"][group_idx]["sensors"][sensor_idx]
            base_name = current_name.split('_')[0]

            # Increment update counter
            sensor_updates[base_name] += 1
            new_name = f"{base_name}_u{sensor_updates[base_name]}"

            # Update the sensor name in the config
            full_config["groups"][group_idx]["sensors"][sensor_idx] = new_name

            # Update version
            full_config["version"] = version

            # Publish full config and info
            await js.publish(CONFIG_FULL_SUBJECT, json.dumps(full_config).encode())
            await js.publish(CONFIG_INFO_SUBJECT, json.dumps({"version": version}).encode())

            print(f"Server published updated config version {version}")
    except KeyboardInterrupt:
        print("Server stopped.")
    finally:
        await nc.close()

if __name__ == "__main__":
    asyncio.run(main())
