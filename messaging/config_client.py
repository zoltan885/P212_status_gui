import asyncio
import json
from nats.aio.client import Client as NATS
from nats.js.kv import KeyValue
from nats.js.errors import BucketNotFoundError

NATS_URL = "nats://127.0.0.1:4222"
BUCKET_NAME = "CONFIG_BUCKET"
CONFIG_KEY = "main_config"

last_state = None

async def process_update(update):
    global last_state
    if update.value is None:
        return
    try:
        config = json.loads(update.value)
        if config != last_state:
            print("🔔 Config updated:", config)
            last_state = config
    except Exception as e:
        print(f"⚠️ Error processing update: {e}")

async def get_or_create_kv(js, bucket_name):
    try:
        return await js.key_value(bucket_name)
    except BucketNotFoundError:
        print(f"Bucket '{bucket_name}' not found, creating...")
        return await js.create_key_value(bucket=bucket_name, history=1)

async def main():
    nc = NATS()
    await nc.connect(
        NATS_URL,
        allow_reconnect=True,
        max_reconnect_attempts=-1,
        reconnect_time_wait=2
    )
    print("✅ Connected to NATS!")

    js = nc.jetstream()
    kv = await get_or_create_kv(js, BUCKET_NAME)

    # --- Fetch current state first ---
    try:
        update = await kv.get(CONFIG_KEY)
        if update and update.value:
            await process_update(update)
    except Exception:
        pass  # Key may not exist yet

    # --- Start watching for future updates ---
    while True:
        try:
            watcher = await kv.watch(CONFIG_KEY)
            async for update in watcher:
                asyncio.create_task(process_update(update))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"⚠️ Watcher error: {e}, retrying in 3s...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Client shutting down...")
