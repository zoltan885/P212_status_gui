'''
Clients send a request message on a "sensors.snapshot.request" subject with a reply inbox

Server listens to "sensors.snapshot.request", and when a request comes, it sends the latest full snapshot back to the reply inbox

Client waits for this reply before subscribing to incremental updates

'''

import asyncio
import nkeys
import base64
import time
import json
import gzip
from nats.aio.client import Client as NATS
from load_credits import parse_creds

CRED_PATH = "/home/hegedues/prog/nats/NGS-Default-CLI.creds"
MEASURE_DELAY = True  # Set to True to measure delay in updates
VERBOSE = True  # Set to True for verbose output

def is_gzipped(data: bytes) -> bool:
    return data[:2] == b'\x1f\x8b'

def decode_message(data: bytes) -> dict:
    if is_gzipped(data):
        decompressed = gzip.decompress(data)
    else:
        decompressed = data
    return json.loads(decompressed.decode("utf-8"))


# Store full sensor state here
full_state = {}
last_update_time = 0

async def snapshot_response_handler(msg):
    global full_state
    full_state = decode_message(msg.data)
    print("Received full snapshot via request:", full_state)

async def incremental_update_handler(msg):
    #print('IUH called')
    global full_state
    global last_update_time
    #update = json.loads(msg.data.decode())
    update = decode_message(msg.data)
    full_state.update(update)
    #print(update)
    if MEASURE_DELAY:
        try:
            delay  = time.time() - float(update[list(update.keys())[0]]['timestamp'])
        except (KeyError, ValueError):
            delay = None
        if VERBOSE:
            print(f"Update: {update}, Delay: {1000*delay:6.1f} ms, DT: {1000*(time.time() - last_update_time):6.1f} ms")
        else:
            print(f"Delay: {1000*delay:6.1f} ms, DT: {1000*(time.time() - last_update_time):6.1f} ms")
    else:
        if VERBOSE:
            print(f"Update: {update}")
        else:
            print(f'Update received')
    last_update_time = time.time()
    

async def request_full_snapshot(nc):
    """
    Request the full snapshot with request-reply and wait for response.
    """
    response = await nc.request("sensors.snapshot.request", b"", timeout=5)
    return json.loads(response.data.decode())

async def main():
    global full_state
    jwt, seed = parse_creds(CRED_PATH)
    kp = nkeys.from_seed(seed.encode())

    nc = NATS()

    await nc.connect(
        servers=["tls://connect.ngs.global:4222"],
        user_jwt_cb=lambda: jwt.encode("utf-8"),
        signature_cb=lambda nonce: base64.b64encode(kp.sign(nonce.encode())),
        name="jwt-subscriber",
    )

    # Step 1: Request full snapshot on demand
    #full_state = await request_full_snapshot(nc)
    #print("Initial full state received:", full_state)

    # Step 2: Subscribe to incremental updates for live data
    await nc.subscribe("sensors.updates", cb=incremental_update_handler)

    # Just keep running and processing messages
    while True:
        await asyncio.sleep(0.01)

asyncio.run(main())