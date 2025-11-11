import asyncio
import json
from nats.aio.client import Client as NATS
from nats.js.errors import BucketAlreadyExistsError

NATS_URL = "nats://127.0.0.1:4222"
BUCKET_NAME = "CONFIG_BUCKET"
CONFIG_KEY = "main_config"

async def get_or_create_kv(js, bucket_name):
    try:
        return await js.key_value(bucket_name)
    except Exception:
        print(f"Bucket '{bucket_name}' not found, creating...")
        return await js.create_key_value(bucket=bucket_name, history=1)

async def publish_config(kv, config_data):
    """Publish or update the configuration"""
    data_bytes = json.dumps(config_data).encode()
    await kv.put(CONFIG_KEY, data_bytes)
    print(f"✅ Published config: {config_data}")

async def main():
    nc = NATS()
    await nc.connect(NATS_URL)
    print("✅ Connected to NATS!")

    js = nc.jetstream()
    kv = await get_or_create_kv(js, BUCKET_NAME)

    # Example: periodically update configuration
    config_version = 1
    while True:
        config = {
            "version": config_version,
            "message": f"This is config version {config_version}"
        }
        await publish_config(kv, config)
        config_version += 1
        await asyncio.sleep(5)  # update every 5 seconds

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server shutting down...")
