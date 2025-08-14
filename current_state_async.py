
import asyncio
from collections import deque
import logging
from asyncio import Queue, Lock
import time
import threading


class OverwritingDualModeQueue:
    """
    A thread-safe + asyncio-safe queue with one-slot overwrite behavior.

    - If maxsize == 1, new items replace the old item instead of blocking.
    - Supports async and sync put/get.
    - task_done() and join() work like normal Queue.
    - Preserves most of asyncio.Queue's API.
    """

    def __init__(self, maxsize=1, loop=None):
        if maxsize != 1:
            raise ValueError("This implementation is optimized for maxsize=1 overwrite behavior")
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._loop = loop or asyncio.get_event_loop()
        self._lock = threading.Lock()

    # ----------------
    # ASYNC METHODS
    # ----------------
    async def put(self, item):
        await self._put_async(item)

    async def get(self):
        return await self._queue.get()

    async def get_nowait(self):
        return self._queue.get_nowait()

    async def join(self):
        await self._queue.join()

    async def empty(self):
        return self._queue.empty()

    async def full(self):
        return self._queue.full()

    async def qsize(self):
        return self._queue.qsize()

    # ----------------
    # THREAD-SAFE SYNC METHODS
    # ----------------
    def put_threadsafe(self, item):
        self._put_threadsafe(item)

    def get_threadsafe(self):
        fut = asyncio.run_coroutine_threadsafe(self._queue.get(), self._loop)
        return fut.result()

    def get_nowait_threadsafe(self):
        with self._lock:
            return self._queue.get_nowait()

    def join_threadsafe(self):
        fut = asyncio.run_coroutine_threadsafe(self._queue.join(), self._loop)
        return fut.result()

    def empty_threadsafe(self):
        with self._lock:
            return self._queue.empty()

    def full_threadsafe(self):
        with self._lock:
            return self._queue.full()

    def qsize_threadsafe(self):
        with self._lock:
            return self._queue.qsize()

    # ----------------
    # TASK TRACKING
    # ----------------
    def task_done(self):
        pass

    # ----------------
    # INTERNAL HELPERS
    # ----------------
    async def _put_async(self, item):
        # If full, drop the old one and mark it done
        removed = False
        try:
            self._queue.get_nowait()
            removed = True
        except asyncio.QueueEmpty:
            pass
        if removed:
            self._queue.task_done()
        await self._queue.put(item)

    def _put_threadsafe(self, item):
        with self._lock:
            removed = False
            try:
                self._queue.get_nowait()
                removed = True
            except asyncio.QueueEmpty:
                pass
            if removed:
                self._queue.task_done()
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)





class AsyncOverwritingSingleSlotQueue(Queue):
    """
    An asynchronous, thread-safe queue with a single slot that overwrites its contents.

    This queue holds at most one item at a time. When a new item is put into the queue,
    it replaces the existing item if present. All operations are protected by an asyncio lock
    to ensure thread safety in asynchronous contexts.

    Methods
    -------
    put(item):
        Asynchronously adds an item to the queue, overwriting any existing item.

    get(timeout=None):
        Asynchronously retrieves the current item from the queue, or waits up to `timeout` seconds.
        Returns None if the queue is empty after waiting.

    empty():
        Asynchronously checks if the queue is empty.

    Example
    -------
        queue = AsyncOverwritingSingleSlotQueue()
        await queue.put("data")
        item = await queue.get(timeout=5)
        is_empty = await queue.empty()
    """
    def __init__(self):
        self._queue = deque(maxlen=1)
        self._lock = asyncio.Lock()
        self._item_available = asyncio.Event()

    async def put(self, item):
        async with self._lock:
            self._queue.append(item)  # Automatically discards old item
            self._item_available.set()  # Signal that item is available

    async def get(self, timeout=None):
        try:
            # Wait until an item is available or timeout expires
            await asyncio.wait_for(self._item_available.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Timeout expired, no item available
            return None

        async with self._lock:
            if not self._queue:
                # Item might have been consumed meanwhile
                self._item_available.clear()
                return None
            item = self._queue[0]
            self._queue.clear()
            self._item_available.clear()
            return item

    async def get_nowait(self):
        """Get item without waiting, returns None if empty."""
        self.get(timeout=0)

    async def empty(self):
        async with self._lock:
            return len(self._queue) == 0
        

UPDATE_INTERVAL = 0.5  # seconds
UPDATE_INTERVAL_MIN = 0.1  # seconds
UPDATE_INTERVAL_MAX = 5.0  # seconds
SNAPSHOT_INTERVAL = 2.0  # seconds
SNAPSHOT_INTERVAL_MIN = 1  # seconds
SNAPSHOT_INTERVAL_MAX = 300  # seconds

RTOL = 1e-3  # relative tolerance for float comparison
ATOL = 1e-4  # absolute tolerance for float comparison

DEBUG = False  # set to True to enable debug logging


class CurrentStateMonitorAsync:

    def __init__(self,
                 in_queue: Queue = None,
                 update_queue: Queue = None,
                 snapshot_queue: asyncio.LifoQueue | Queue = None):
        self.in_queue = in_queue or asyncio.Queue()
        self.update_queue = update_queue or asyncio.Queue()
        self.snapshot_queue = snapshot_queue or asyncio.Queue()

        self.filtered_messages = deque([], maxlen=10000)
        self.state = {}

        self._lock = Lock()
        self._update_interval = UPDATE_INTERVAL
        self._snapshot_interval = SNAPSHOT_INTERVAL

        # Asyncio Events to control updating and snapshotting
        self._update_pause = asyncio.Event()
        self._update_pause.set()  # Initially paused
        self._update_stop = asyncio.Event()
        self._snapshot_pause = asyncio.Event()
        self._snapshot_pause.set()  # Initially paused
        self._snapshot_stop = asyncio.Event()


        # Asyncio tasks for updating and snapshotting
        self._update_task = None
        self._snapshot_task = None

    def _isclose(self, a, b, rtol=RTOL, atol=ATOL):
        abs_diff = abs(a - b)
        rel_diff = abs_diff / max(abs(a), abs(b), 1e-30)
        abs_fail = abs_diff > atol
        rel_fail = rel_diff > rtol
        return not (abs_fail or rel_fail)

    def _value_changed(self, old_value, new_value):
        if isinstance(old_value, (float, int)) and isinstance(new_value, (float, int)):
            return not self._isclose(old_value, new_value, rtol=RTOL, atol=ATOL)
        elif isinstance(old_value, str) and isinstance(new_value, str):
            return old_value != new_value
        return old_value != new_value

    def _state_changed(self, old_state, new_state):
        return old_state != new_state

    @property
    def update_interval(self):
        return self._update_interval
    @update_interval.setter
    def update_interval(self, value):
        value = abs(float(value))
        if value < UPDATE_INTERVAL_MIN:
            self._update_interval = UPDATE_INTERVAL_MIN
        elif value > UPDATE_INTERVAL_MAX:
            self._update_interval = UPDATE_INTERVAL_MAX
        else:
            self._update_interval = value

    @property
    def snapshot_interval(self):
        return self._snapshot_interval
    @snapshot_interval.setter
    def snapshot_interval(self, value):
        value = abs(float(value))
        if value < SNAPSHOT_INTERVAL_MIN:
            self._snapshot_interval = SNAPSHOT_INTERVAL_MIN
        elif value > SNAPSHOT_INTERVAL_MAX:
            self._snapshot_interval = SNAPSHOT_INTERVAL_MAX
        else:
            self._snapshot_interval = value

    async def filter_messages(self):
        self.filtered_messages.clear()
        async with self._lock:
            while not self.in_queue.empty():
                try:
                    msg = await asyncio.wait_for(self.in_queue.get(), timeout=0.01)
                    #logging.info(f"Got message: {msg}")
                    ID = msg['ID']
                    value = msg['value']
                    state = msg['state']
                    timestamp = msg['timestamp']

                    if ID in self.state:
                        if self._value_changed(self.state[ID]['value'], value) or \
                           self._state_changed(self.state[ID]['state'], state):
                            self.state[ID] = msg
                            # Update filtered_messages: keep only latest per ID
                            for i in range(len(self.filtered_messages)):
                                if self.filtered_messages[i]['ID'] == ID:
                                    self.filtered_messages[i] = msg
                                    break
                            else:
                                self.filtered_messages.append(msg)
                    else:
                        self.state[ID] = msg
                        self.filtered_messages.append(msg)
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logging.error("Exception in filter_messages: %s", e)
                    break

    async def snapshot(self):
        snapshot = []
        async with self._lock:
            # It would be nicer to use a custom queue that supports overwriting,
            # but for now we clear the snapshot queue if it has items.
            # This should ensure that we only keep the latest snapshot.
            # Additionally one could use a LifoQueue for added safety.
            while not self.snapshot_queue.empty():
                _ = await self.snapshot_queue.get()  # clear it if not empty
            for ID, msg in self.state.items():
                snapshot.append(msg)
            if snapshot:
                await self.snapshot_queue.put(snapshot)

    async def update(self):
        await self.filter_messages()
        async with self._lock:
            if self.update_queue is not None:
                while len(self.filtered_messages) > 0:
                    msg = self.filtered_messages.popleft()
                    await self.update_queue.put(msg)
            else:
                logging.error('No update queue set, cannot send message')

    async def start_update(self):
        """
        Start the updating task and unpause updating.
        """
        self._update_pause.clear()
        if self._update_task is None or self._update_task.done():
            self._update_task = asyncio.create_task(self._update_worker())

    async def start_snapshot(self):
        """
        Start the snapshotting task and unpause snapshotting.
        """
        self._snapshot_pause.clear()
        if self._snapshot_task is None or self._snapshot_task.done():
            self._snapshot_task = asyncio.create_task(self._snapshot_worker())

    async def pause_self_update(self):
        """
        Pause updating
        """
        self._update_pause.set()

    async def stop_update(self):
        """
        Stop updating
        """
        self._update_stop.set()
        if self._update_task:
            await self._update_task

    async def start_snapshot(self):
        """
        Start the snapshotting task and unpause snapshotting.
        """
        self._snapshot_pause.clear()
        if self._snapshot_task is None or self._snapshot_task.done():
            self._snapshot_task = asyncio.create_task(self._snapshot_worker())

    async def pause_self_snapshot(self):
        """
        Pause snapshotting
        """
        self._snapshot_pause.set()

    async def stop_snapshot(self):
        """
        Stop snapshotting
        """
        self._snapshot_stop.set()
        if self._snapshot_task:
            await self._snapshot_task

    async def _update_worker(self):
        while not self._update_stop.is_set():
            if not self._update_pause.is_set():
                try:
                    await self.update()
                except Exception as e:
                    logging.error('Error in update worker: %s', e)
            else:
                await asyncio.sleep(0.1)  # Sleep a bit while paused
            await asyncio.sleep(self.update_interval)

    async def _snapshot_worker(self):
        while not self._snapshot_stop.is_set():
            if not self._snapshot_pause.is_set():
                try:
                    await self.snapshot()
                except Exception as e:
                    logging.error('Error in snapshot worker: %s', e)
            await asyncio.sleep(self.snapshot_interval)

    # async def __aenter__(self):
    #     # To support async context manager usage
    #     await self.start_update()
    #     return self

    # async def __aexit__(self, exc_type, exc_val, exc_tb):
    #     await self.stop_update()

    def __del__(self):
        # best-effort cleanup
        try:
            if not self._update_stop.is_set():
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.stop_update())
            if not self._snapshot_stop.is_set():
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.stop_snapshot())
        except Exception:
            pass
        logging.info('CurrentStateMonitor instance deleted, reporting stopped.')