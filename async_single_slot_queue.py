
'''
This construct could be use in the current_state.py, but then it needs to be adapted to use asyncio.
'''



import asyncio
from collections import deque

class AsyncOverwritingSingleSlotQueue:
    """
    An asynchronous, thread-safe queue with a single slot that overwrites its contents.

    This queue holds at most one item at a time. When a new item is put into the queue,
    it replaces the existing item if present. All operations are protected by an asyncio lock
    to ensure thread safety in asynchronous contexts.

    Methods
    -------
    put(item):
        Asynchronously adds an item to the queue, overwriting any existing item.

    get():
        Asynchronously retrieves the current item from the queue, or returns None if empty.

    empty():
        Asynchronously checks if the queue is empty.

    Example
    -------
        queue = AsyncOverwritingSingleSlotQueue()
        await queue.put("data")
        item = await queue.get()
        is_empty = await queue.empty()
    """
    def __init__(self):
        self._queue = deque(maxlen=1)
        self._lock = asyncio.Lock()

    async def put(self, item):
        async with self._lock:
            self._queue.append(item)  # Automatically discards old item

    async def get(self):
        async with self._lock:
            return self._queue[0] if self._queue else None

    async def empty(self):
        async with self._lock:
            return len(self._queue) == 0



# usage example

import asyncio

async def producer(q):
    for i in range(5):
        await q.put(i)
        print(f"Produced: {i}")
        await asyncio.sleep(0.5)

async def consumer(q):
    while True:
        item = await q.get()
        if item is not None:
            print(f"Consumed: {item}")
        await asyncio.sleep(1)

async def main():
    q = AsyncOverwritingSingleSlotQueue()
    await asyncio.gather(
        producer(q),
        consumer(q)
    )

asyncio.run(main())