import asyncio
import nkeys
import base64
import time
import json
import gzip
from nats.aio.client import Client as NATS
from load_credits import parse_creds


CRED_PATH = "/home/p212user/zoltan/P212_status_gui/credits.creds"
USE_GZIP = True  # Set to True to enable gzip compression

def is_gzipped(data: bytes) -> bool:
    return data[:2] == b'\x1f\x8b'

def decode_message(data: bytes) -> dict:
    if is_gzipped(data):
        decompressed = gzip.decompress(data)
    else:
        decompressed = data
    return json.loads(decompressed.decode("utf-8"))

async def main():
    jwt, seed = parse_creds(CRED_PATH)
    kp = nkeys.from_seed(seed.encode())

    nc = NATS()

    await nc.connect(
        servers=["tls://connect.ngs.global:4222"],
        user_jwt_cb=lambda: jwt.encode("utf-8"),
        signature_cb=lambda nonce: base64.b64encode(kp.sign(nonce.encode())),
        name="jwt-subscriber",
    )

    response = await nc.request("sensors.snapshot.request", b"", timeout=5)
    if response:
        snapshot = decode_message(response.data)
        print(f"Received snapshot: {snapshot}")
    else:
        print("No response received.")

if __name__ == "__main__":
    asyncio.run(main())