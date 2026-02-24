'''
Clients send a request message on a "sensors.snapshot.request" subject with a reply inbox

Server listens to "sensors.snapshot.request", and when a request comes, it sends the latest full snapshot back to the reply inbox

Client waits for this reply before subscribing to incremental updates

'''

import asyncio
import nkeys
import base64
import time
import ntplib
import json
import gzip
from nats.aio.client import Client as NATS
from load_credits import parse_creds
from clock_offset_manager import ClockOffsetManager

CRED_PATH = "/home/hegedues/prog/nats/NGS-Default-CLI.creds"
MEASURE_DELAY = True  # Set to True to measure delay in updates
VERBOSE = True  # Set to True for verbose output

SERVER_CLOCK_OFFSET = 0
LAST_OFFSET_TIME = 0
LOCAL_OFFSET = 0
NTP_SERVER = "ntp.desy.de"

def is_gzipped(data: bytes) -> bool:
    return data[:2] == b'\x1f\x8b'

def decode_message(data: bytes) -> dict:
    if is_gzipped(data):
        decompressed = gzip.decompress(data)
    else:
        decompressed = data
    return json.loads(decompressed.decode("utf-8"))

def get_offset(ntp_server=NTP_SERVER): # this is synchronous and blocking.
    global LAST_OFFSET_TIME
    if time.time() - LAST_OFFSET_TIME < 15:  # Cache offset for 15 seconds
        return SERVER_CLOCK_OFFSET
    try:
        client = ntplib.NTPClient()
        response = client.request(ntp_server, version=3, timeout=2)
        LAST_OFFSET_TIME = time.time()
        return response.offset  # seconds
    except Exception:
        return 0

async def get_offset_async(ntp_server=NTP_SERVER):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_offset, ntp_server)

async def _get_server_time_offset(msg):
    offset = float(msg.data.decode().get('server_clock_offset', 0))
    global SERVER_CLOCK_OFFSET
    SERVER_CLOCK_OFFSET = offset
    print(f"Received server clock offset: {SERVER_CLOCK_OFFSET:.3f} seconds")

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
    headers = msg.headers
    if headers:
        encoding = headers.get("encoding", "None")
        producer = headers.get("producer", "Unknown")
        timestamp = float(headers.get("timestamp", "Unknown"))
        message_id = headers.get("message_id", "Unknown")
    else:
        timestamp = time.time()
        message_id = "Unknown"
    full_state.update(update)
    #print(update)
    if MEASURE_DELAY:
        global SERVER_CLOCK_OFFSET
        global LOCAL_OFFSET
        adjusted_timestamp = timestamp + SERVER_CLOCK_OFFSET - LOCAL_OFFSET
        try:
            delay  = time.time() - adjusted_timestamp
        except (KeyError, ValueError):
            delay = None
        if VERBOSE:
            print(f"Update {headers}: {update}, Delay: {1000*delay:6.1f} ms, DT: {1000*(time.time() - last_update_time):6.1f} ms")
        else:
            print(f"Update {message_id}; delay: {1000*delay:6.1f} ms, DT: {1000*(time.time() - last_update_time):6.1f} ms")
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

    COM = ClockOffsetManager()
    await COM.start()

    # Step 1: Request full snapshot on demand
    #full_state = await request_full_snapshot(nc)
    #print("Initial full state received:", full_state)

    # Step 2: Subscribe to incremental updates for live data
    await nc.subscribe("sensors.updates", cb=incremental_update_handler)
    await nc.subscribe("sensor.telemetry", cb=_get_server_time_offset)
    global LOCAL_OFFSET
    LOCAL_OFFSET = await get_offset_async()

    # Just keep running and processing messages
    while True:
        await asyncio.sleep(0.01)

asyncio.run(main())