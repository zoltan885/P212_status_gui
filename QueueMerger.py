import asyncio
from typing import Dict, Tuple, Any, Optional

class QueueMerger:
    """
    Merge multiple named asyncio.Queues into a single output queue.

    - Queues can be added or removed dynamically.
    - Optionally include the source name in merged items.
    - Automatically sends a sentinel (e.g., None) when all queues complete.
    """

    def __init__(self, include_source: bool = False, sentinel: Any = None):
        self.output_queue = asyncio.Queue()
        self.include_source = include_source
        self.sentinel = sentinel
        self._entries: Dict[str, Tuple[asyncio.Queue, asyncio.Task]] = {}
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._done_signal_sent = asyncio.Event()

    async def _forward(self, name: str, q: asyncio.Queue):
        """Forward items from one queue to the output queue."""
        try:
            while not self._stop_event.is_set():
                item = await q.get()
                if item is None:
                    # Sentinel from producer -> stop this queue
                    q.task_done()
                    break
                if self.include_source:
                    item = (name, item)
                await self.output_queue.put(item)
                q.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            # When this forwarder ends, check for global completion
            await self._check_all_done()

    async def _check_all_done(self):
        """If all queues are finished, send sentinel once."""
        async with self._lock:
            # remove finished tasks
            finished = [name for name, (_, task) in self._entries.items() if task.done()]
            for name in finished:
                self._entries.pop(name, None)
            if not self._entries and not self._done_signal_sent.is_set():
                await self.output_queue.put(self.sentinel)
                self._done_signal_sent.set()

    async def add_queue(self, name: str, q: asyncio.Queue):
        """Add a new named queue to be merged."""
        async with self._lock:
            if name in self._entries:
                raise ValueError(f"Queue '{name}' already exists.")
            task = asyncio.create_task(self._forward(name, q))
            self._entries[name] = (q, task)

    async def remove_queue(self, name: str):
        """Remove a queue by name."""
        async with self._lock:
            entry = self._entries.pop(name, None)
            if entry:
                q, task = entry
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await self._check_all_done()

    async def start(self):
        """Prepare for operation (no-op for dynamic version)."""
        self._stop_event.clear()
        self._done_signal_sent.clear()

    async def stop(self):
        """Stop all forwarders gracefully."""
        self._stop_event.set()
        async with self._lock:
            entries = list(self._entries.values())
            self._entries.clear()
        for _, task in entries:
            task.cancel()
        await asyncio.gather(*(t for _, t in entries), return_exceptions=True)
        if not self._done_signal_sent.is_set():
            await self.output_queue.put(self.sentinel)
            self._done_signal_sent.set()

    def get_output_queue(self) -> asyncio.Queue:
        """Return the merged output queue."""
        return self.output_queue

    def list_queues(self):
        """Return a list of active queue names."""
        return list(self._entries.keys())







############### Alternative using anyio #####################

import anyio
import random
import time

# Configuration
N_PRODUCERS = 3
QUEUE_SIZE = 20
MASTER_QUEUE_SIZE = 100
PRODUCE_INTERVAL = (0.05, 0.15)
CONSUME_INTERVAL = 0.1


# ------------------------------------------------
# Producer
# ------------------------------------------------
async def producer(name, send_stream):
    async with send_stream:
        for i in range(200):  # simulate ongoing updates
            await send_stream.send((name, i, time.time()))
            await anyio.sleep(random.uniform(*PRODUCE_INTERVAL))
        print(f"{name} finished producing.")


# ------------------------------------------------
# Adaptive merger
# ------------------------------------------------
async def adaptive_merger(receive_streams, master_send, check_interval=0.2):
    """
    Merge items from all producer streams into master_send,
    adapting to backpressure based on master buffer fill.
    """
    async with master_send:
        async with anyio.create_task_group() as tg:
            # Start a forwarding task per input stream
            for recv in receive_streams:
                tg.start_soon(forward_stream, recv, master_send, check_interval)


async def forward_stream(recv, master_send, check_interval):
    async with recv:
        async for item in recv:
            # Monitor how full the master stream is
            buf = master_send._state.buffer
            buf_size = len(buf)
            buf_max = master_send._state.max_buffer_size

            fill_ratio = buf_size / buf_max if buf_max else 0.0

            # Dynamic adaptation: slow down or speed up
            if fill_ratio > 0.8:
                # Master queue almost full → apply backpressure
                await anyio.sleep(check_interval * 2)
            elif fill_ratio > 0.5:
                # Moderate pressure → slight slowdown
                await anyio.sleep(check_interval * 0.5)

            # Forward message
            await master_send.send(item)


# ------------------------------------------------
# Consumer
# ------------------------------------------------
async def consumer(master_recv):
    async with master_recv:
        async for (name, value, ts) in master_recv:
            # Simulate varying processing load
            await anyio.sleep(CONSUME_INTERVAL * random.uniform(0.8, 1.5))
            print(f"[{name}] val={value} time={ts:.3f}")


# ------------------------------------------------
# Monitor (optional)
# ------------------------------------------------
async def monitor(master_send, interval=1.0):
    while True:
        buf = master_send._state.buffer
        buf_size = len(buf)
        buf_max = master_send._state.max_buffer_size
        fill_ratio = buf_size / buf_max if buf_max else 0
        print(f"[MONITOR] master buffer {buf_size}/{buf_max} ({fill_ratio*100:.1f}%)")
        await anyio.sleep(interval)


# ------------------------------------------------
# Main
# ------------------------------------------------
async def main():
    recv_streams = []
    producers = []

    # Create individual producer streams
    for i in range(N_PRODUCERS):
        send, recv = anyio.create_memory_object_stream(max_buffer_size=QUEUE_SIZE)
        producers.append((f"producer{i+1}", send))
        recv_streams.append(recv)

    # Create master output stream
    master_send, master_recv = anyio.create_memory_object_stream(max_buffer_size=MASTER_QUEUE_SIZE)

    async with anyio.create_task_group() as tg:
        # Producers
        for name, send in producers:
            tg.start_soon(producer, name, send)

        # Adaptive merger
        tg.start_soon(adaptive_merger, recv_streams, master_send)

        # Consumer
        tg.start_soon(consumer, master_recv)

        # Monitor (optional)
        tg.start_soon(monitor, master_send, 1.0)

anyio.run(main)
