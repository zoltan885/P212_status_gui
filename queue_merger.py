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








