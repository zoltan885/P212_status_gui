
import logging
from queue import Queue, Empty
import json
import time
import asyncio
import gzip
import base64
import nkeys
from nats.aio.client import Client as NATS
import threading
from threading import Event

from load_credits import parse_creds
from current_state import OverwritingSingleSlotQueue



CRED_PATH = "./credits.creds"
USE_GZIP = True  # Set to True to enable gzip compression
VERBOSE = False


class UpdatePublisher:
    def __init__(self, update_queue: Queue, topic: str = "sensors.updates"):
        self.update_queue = update_queue
        self._publish_time_constant = 0.5  # seconds
        self.topic = topic

        self.publish_event = Event()
        self.publish_event.clear()
        self._shutdown_event = Event()
        self._shutdown_event.clear()
        self.state = "not ready"
        self.t0 = time.time()
        self.last_publish_time = 0

    async def _init_nats_publisher(self):
        logging.info("Initializing NATS connection...")
        jwt, seed = parse_creds(CRED_PATH)
        kp = nkeys.from_seed(seed.encode())
        self.nc = NATS()
        
        await self.nc.connect(
            servers=["tls://connect.ngs.global:4222"],
            user_jwt_cb=lambda: jwt.encode("utf-8"),
            signature_cb=lambda nonce: base64.b64encode(kp.sign(nonce.encode())),
            name="jwt-python-publisher",
        )

    async def setup(self):
        """
        Initialize the NATS connection and set up the publisher.
        """
        await self._init_nats_publisher()
        asyncio.create_task(self._publish_updates(self.topic))
        self.state = "ready"

    @property
    def publish_time_constant(self):
        return self._publish_time_constant
    @publish_time_constant.setter
    def publish_time_constant(self, value):
        try:
            value = float(value)
        except ValueError:
            raise ValueError("Time constant must be a number")
        if value < 0.2:
            self._publish_time_constant = 0.2
        elif value > 5.0:
            self._publish_time_constant = 5.0
        else:
            self._publish_time_constant = value

    async def _publish_updates(self, topic: str):
        """
        Publish updates from the update queue to NATS.
        """
        while True:
            start = time.monotonic()
            dct = {}
            ctr = 1
            while self.update_queue.qsize() > 0:
                try:
                    item = self.update_queue.get_nowait()
                    if item is None:
                        continue
                    dct[ctr] = item
                    ctr += 1
                except Empty:
                    break
                except Exception as e:
                    logging.error(f"Error getting item from update queue: {e}")
                    break
            if self.publish_event.is_set() and dct != {}:
                    if VERBOSE:
                        logging.info(dct)
                    encoded_data = self._encode_data(dct, USE_GZIP)
                    await self.nc.publish(topic, encoded_data)
                    logging.info(f"Published update to {topic} @ {time.time() - self.t0:.2f} s, dt = {1000*(time.time() - self.last_publish_time):.2f} ms")
                    self.last_publish_time = time.time()
            elapsed = time.monotonic() - start
            sleep_time = max(0, self._publish_time_constant - elapsed)
            await asyncio.sleep(sleep_time)

    def _encode_data(self, data: dict, use_gzip: bool) -> bytes:
        bytedata = json.dumps(data).encode("utf-8")
        if use_gzip:
            return gzip.compress(bytedata)
        else:
            return bytedata



class SnapshotWorker:
    def __init__(self, snapshot_queue: Queue, topic: str = "sensors.snapshot", request_topic: str = "sensors.snapshot.request"):
        self.snapshot_queue = snapshot_queue
        self.topic = topic
        self.request_topic = request_topic
        self._shutdown_event = Event()
        self._shutdown_event.clear()
        self.publish_periodic = False
        self.publish_period = 2
        self.state = "not ready"
        self.t0 = time.time()
        self.last_snapshot_time = 0

    async def setup(self):
        """
        Initialize the NATS connection and set up the snapshot responder.
        """
        await self._init_nats_responder()
        asyncio.create_task(self._periodic_snapshot_publisher())
        self.state = "ready"
    
    async def _init_nats_responder(self):
        """
        Initialize the NATS responder for snapshot requests.
        """
        self.nc = NATS()
        jwt, seed = parse_creds(CRED_PATH)
        kp = nkeys.from_seed(seed.encode())
        await self.nc.connect(
            servers=["tls://connect.ngs.global:4222"],
            user_jwt_cb=lambda: jwt.encode("utf-8"),
            signature_cb=lambda nonce: base64.b64encode(kp.sign(nonce.encode())),
            name="jwt-python-publisher",
        )
        await self.nc.subscribe(self.request_topic, cb=self._snapshot_request_handler)
        logging.info("NATS snapshot request handler initialized.")

    async def publish_snapshot(self,):
        """
        Publish a snapshot to the snapshot queue.
        """
        # wait for snapshot to be available
        snapshot = None
        while not snapshot:
            try:
                snapshot = await self.snapshot_queue.get()
            except (Empty, TimeoutError):
                await asyncio.sleep(1)

        if self.nc and self.nc.is_connected:
            snapshot_json = json.dumps(snapshot).encode()
            await self.nc.publish("sensors.snapshot", snapshot_json)
        else:
            logging.warning("NATS connection not established, cannot publish snapshot.")

    async def _snapshot_request_handler(self, msg):
        """
        Respond to snapshot requests with the current full snapshot.
        """
        # wait for snapshot to be available
        snapshot = None
        while not snapshot:
            try:
                snapshot = await self.snapshot_queue.get()
            except Empty:
                await asyncio.sleep(1)  
        
        reply = msg.reply
        if reply:
            if self.nc and self.nc.is_connected:
                snapshot_json = json.dumps(snapshot).encode()
                await self.nc.publish(reply, snapshot_json)
            logging.info(f"Sent snapshot response to {reply}")


    async def _periodic_snapshot_publisher(self):
        """
        periodically publish full snapshots
        """
        while True:
            start = time.monotonic()
            if self.publish_periodic:
                await self.publish_snapshot()
                logging.info(f"Published full snapshot to sensors.state at {time.time()-self.t0:.2f} s, dt = {1000*(time.time() - self.last_snapshot_time):.2f} ms")
            self.last_snapshot_time = time.time()
            elapsed = time.monotonic() - start
            sleep_time = max(0, self.publish_period - elapsed)
            await asyncio.sleep(sleep_time)





async def test_update_publisher():
    """
    Test function to run the publisher.
    """
    update_queue = Queue()
    
    publisher = UpdatePublisher(update_queue)
    print(f'Publisher initialized, setting up... state = {publisher.state}')
    await publisher.setup()
    print(f'Publisher setup complete, state = {publisher.state}')
    
    # Start publishing updates
    #topic = "sensors.updates"
    #asyncio.create_task(publisher._publish_updates(topic))
    
    # Optionally, start periodic snapshot publishing
    # asyncio.create_task(publisher._periodic_snapshot_publisher(jetstream, snapshot))
    
    print("Putting stuff in the update queue...")
    # Simulate some updates
    for i in range(10):
        update_queue.put({"sensor": f"sensor_{i}", "value": i, "timestamp": time.time()})
        print(i)
        await asyncio.sleep(0.3)
 

    print(f"Updates in queue: {update_queue.qsize()}")

    publisher.publish_event.set()  # Trigger publishing
    # Simulate some updates
    for i in range(100):
        update_queue.put({"sensor": f"sensor_{i}", "value": i, "timestamp": time.time()})
        print(i)
        await asyncio.sleep(0.1)  # simulate time between updates

    print("Updates should be published now.")


async def test_snapshot_worker():
    """
    Test function to run the snapshot worker.
    """
    
    snapshot_queue = OverwritingSingleSlotQueue()
    
    worker = SnapshotWorker(snapshot_queue, topic="sensors.snapshot")
    print(f'SnapshotWorker initialized, setting up... state = {worker.state}')
    await worker.setup()
    print(f'SnapshotWorker setup complete, state = {worker.state}')
    
    # Simulate some snapshots
    for i in range(5):
        snapshot_queue.put({"snapshot": f"snapshot_{i}", "timestamp": time.time()})
        print(i)
        await asyncio.sleep(0.5)  # simulate time between snapshots

    await worker.publish_snapshot()

    worker.publish_periodic = True  # Enable periodic publishing
    print("Periodic snapshot publishing enabled.")
    for i in range(50):
        snapshot_queue.put({"snapshot": f"snapshot_{i}", "timestamp": time.time()})
        await asyncio.sleep(0.5)  # simulate time between snapshots

async def test_snapshot_request_handler():
    """
    Test function to run the snapshot request handler.
    """
    snapshot_queue = OverwritingSingleSlotQueue()
    
    worker = SnapshotWorker(snapshot_queue, topic="sensors.snapshot", request_topic="sensors.snapshot.request")
    print(f'SnapshotWorker initialized, setting up... state = {worker.state}')
    await worker.setup()
    print(f'SnapshotWorker setup complete, state = {worker.state}')
    
    # Simulate some snapshots
    for i in range(100):
        snapshot_queue.put({"snapshot": f"snapshot_{i}", "timestamp": time.time()})
        print(i)
        await asyncio.sleep(0.5)  # simulate time between snapshots


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    #asyncio.run(test_update_publisher())
    #asyncio.run(test_snapshot_worker())
    asyncio.run(test_snapshot_request_handler())