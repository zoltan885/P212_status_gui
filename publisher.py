'''
This has gotten a little bit out of hand.

The idea is to have a AsyncFanOutDispatcher, that can be used to publish messages to multiple subscribers.
Then multiple agents (e.g., nats, zmq for internal use) can subscribe to the same topics, and process messages concurrently.
The NATSAgent is a specific implementation that connects to a NATS server and publishes messages to it.
The whole thing is completely untested, and is a work in progress.

'''




import logging
import zmq
from queue import Queue, Empty
import json
import time
import asyncio
import gzip
import base64
import nkeys
from nats.aio.client import Client as NATS
import threading
from collections import deque, defaultdict
from typing import Any, Dict, List, Optional

from load_credits import parse_creds



CRED_PATH = "/home/p212user/zoltan/P212_status_gui/credits.creds"
USE_GZIP = True  # Set to True to enable gzip compression
PUBLSIH_SNAPSHOT = False  # Set to True to publish full snapshot on startup

class FanOutDispatcher:
    def __init__(self):
        self.subscribers = []
        self.lock = threading.Lock()

    def subscribe(self):
        """Each subscriber gets its own queue."""
        q = deque(maxlen=1000)
        with self.lock:
            self.subscribers.append(q)
        return q

    def publish(self, item):
        """Push item to all subscriber queues."""
        with self.lock:
            for q in self.subscribers:
                q.put(item)

    def unsubscribe(self, q):
        with self.lock:
            self.subscribers.remove(q)


class AsyncFanOutDispatcher:
    '''
    An asynchronous version of FanOutDispatcher that uses asyncio Queues, and allows for
    subscribing to topics with a maximum queue size.
    Subscribers can be added and removed dynamically, and the dispatcher can handle publishing
    messages to all subscribers of a given topic.
    '''
    def __init__(self, max_queue_size: int = 1000):
        self.topic_subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self.max_queue_size = max_queue_size
        self._lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()

    async def subscribe(self, topic: str) -> asyncio.Queue:
        """Subscribe to a topic. Returns an asyncio.Queue."""
        q = asyncio.Queue(maxsize=self.max_queue_size)
        async with self._lock:
            self.topic_subscribers[topic].append(q)
        return q

    async def unsubscribe(self, topic: str, q: asyncio.Queue):
        """Remove a subscriber from a topic."""
        async with self._lock:
            if q in self.topic_subscribers[topic]:
                self.topic_subscribers[topic].remove(q)
            if not self.topic_subscribers[topic]:
                del self.topic_subscribers[topic]

    async def publish(self, topic: str, item: Any, timeout: float = None):
        """Send an item to all subscribers of the given topic."""
        async with self._lock:
            subscribers = list(self.topic_subscribers.get(topic, []))
        for q in subscribers:
            try:
                if timeout is not None:
                    await asyncio.wait_for(q.put(item), timeout)
                else:
                    await q.put(item)
            except asyncio.TimeoutError:
                print(f"[WARN] Timeout publishing to a subscriber on topic '{topic}'")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ERROR] Failed to publish to queue: {e}")

    async def shutdown(self):
        """Signal shutdown to all subscribers."""
        self._shutdown_event.set()
        async with self._lock:
            for topic, queues in self.topic_subscribers.items():
                for q in queues:
                    await q.put(None)  # Sentinel for shutdown
            self.topic_subscribers.clear()

    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.shutdown()


class AsyncAgent:
    def __init__(self, name: str, dispatcher, topics: List[str]):
        self.name = name
        self.dispatcher = dispatcher
        self.topics = topics
        self.queues: Dict[str, asyncio.Queue] = {}
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Subscribe to all topics and start listening tasks."""
        for topic in self.topics:
            queue = await self.dispatcher.subscribe(topic)
            self.queues[topic] = queue
            task = asyncio.create_task(self._listen_to_topic(topic, queue))
            self._tasks.append(task)
            logging.info(f"[{self.name}] Subscribed to topic '{topic}'.")
        self._running = True

    async def stop(self):
        """Stop all listener tasks and unsubscribe from all topics."""
        self._running = False

        for topic, queue in self.queues.items():
            await self.dispatcher.unsubscribe(topic, queue)
            logging.info(f"[{self.name}] Unsubscribed from topic '{topic}'.")

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.queues.clear()
        self._tasks.clear()
        logging.info(f"[{self.name}] All listeners stopped.")

    async def _listen_to_topic(self, topic: str, queue: asyncio.Queue):
        """Listen to a specific topic queue."""
        while self._running and not self.dispatcher.is_shutting_down():
            item = await queue.get()
            if item is None:
                break
            await self.handle_message(topic, item)

    async def handle_message(self, topic: str, item):
        """Override this in subclasses to process incoming messages."""
        logging.info(f"[{self.name}] ({topic}) Received: {item}")
        await asyncio.sleep(0.1)  # simulate work

class NATSAgent(AsyncAgent):
    def __init__(self, name: str, dispatcher, topics: List[str]):
        super().__init__(name, dispatcher, topics)
        self.jwt, seed = parse_creds(CRED_PATH)
        self.kp = nkeys.from_seed(seed.encode())
        self.nc: Optional[NATS] = None

    def _encode_data(self, data: dict, use_gzip: bool) -> bytes:
        bytedata = json.dumps(data).encode("utf-8")
        if use_gzip:
            return gzip.compress(bytedata)
        else:
            return bytedata

    async def start(self):
        # Connect to NATS first
        self.nc = NATS()
        await self.nc.connect(
            servers=["tls://connect.ngs.global:4222"],
            user_jwt_cb=lambda: self.jwt.encode("utf-8"),
            signature_cb=lambda nonce: base64.b64encode(self.kp.sign(nonce.encode())),
            name="jwt-python-publisher",
        )
        logging.info(f"[{self.name}] Connected to NATS")
        
        # Then start the parent logic (subscribe to dispatcher)
        await super().start()

    async def stop(self):
        # Stop the base agent logic
        await super().stop()
        
        # Disconnect from NATS
        if self.nc and self.nc.is_connected:
            await self.nc.drain()
            logging.info(f"[{self.name}] Disconnected from NATS.")

    async def handle_message(self, topic: str, item: dict):
        # Override to publish to NATS
        if self.nc and self.nc.is_connected:
            await self.nc.publish(topic.encode(), self._encode_data(item, USE_GZIP))
            logging.debug(f"[{self.name}] Published to NATS ({topic}): {item}")


async def main():
    async with AsyncFanOutDispatcher() as dispatcher:
        agent = NATSAgent("nats1", dispatcher, ["sensor.updates", "alerts"])
        await agent.start()

        await dispatcher.publish("sensor.updates", {"cpu": 78.2})
        await dispatcher.publish("alerts", "Overheating warning")

        await asyncio.sleep(1)
        await agent.stop()

asyncio.run(main())





