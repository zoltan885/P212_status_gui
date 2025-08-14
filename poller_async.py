import logging
import time
import threading
import asyncio
from collections import deque, namedtuple
import tango
import utilities

log = logging.getLogger(__name__)

GRACE = 0.1
LOGTIME = 1
DEQUEUE_MAX_SIZE = 2000
VERBOSE = False

logtuple = namedtuple('log', ['time', 'value'])
tasktuple = namedtuple('task', ['index', 'task'])
statetuple = namedtuple('state', ['value', 'state'])


class AsyncPoller:
    """
    Async Poller with sync/async API compatibility.

    You can call add_attr(), start(), pause(), resume(), stop()
    from either synchronous or asynchronous code.
    """

    def __init__(self, queue: asyncio.Queue):
        self.startEvent = asyncio.Event()
        self.pauseEvent = asyncio.Event()
        self.stopEvent = asyncio.Event()

        self.queue = queue
        self._tasks_dct = {}
        self.log = {}
        self.current_state = {}
        self.last_state = []
        self._grace = GRACE

        self._loop = None
        self._loop_thread = None

    # ------------------------
    # Public methods (context-aware)
    # ------------------------
    def add_attr(self, *args, **kwargs):
        return self._call_context_aware(self._add_attr_async(*args, **kwargs))

    def start(self):
        return self._call_context_aware(self._start_async())

    def pause(self):
        return self._call_context_aware(self._pause_async())

    def resume(self):
        return self._call_context_aware(self._resume_async())

    def stop(self):
        return self._call_context_aware(self._stop_async(), stop_loop=True)

    # ------------------------
    # Async core methods
    # ------------------------
    async def _add_attr_async(self, attrdct: dict, state: bool = False, name: str = None):
        dev = attrdct['dev']
        attr = attrdct['attr']
        logged = attrdct.get('logged', False)

        ID = utilities.create_ID(attrdct)
        if ID in self._tasks_dct:
            log.info(f'Task with ID {ID} already exists')
            return

        try:
            attrProxy = tango.AttributeProxy(f"{dev}/{attr}")
            log.info(f'Created attribute proxy: {dev}/{attr}')
        except Exception:
            log.error(f'Could not create attribute proxy: {dev}/{attr}')
            return

        devProxy = None
        if state:
            try:
                devProxy = attrProxy.get_device_proxy()
                log.info(f'Created device proxy: {dev}')
            except Exception:
                log.error(f'Could not create device proxy: {dev}')
                return

        index = len(self._tasks_dct) + 1
        task = asyncio.create_task(
            self._attribute_worker(
                index=index,
                ID=ID,
                attrProxy=attrProxy,
                devProxy=devProxy,
                queue=self.queue,
                logged=logged,
                name=name,
            )
        )

        if logged:
            log.debug(f'Added logged attribute {attr}')
            self.log[ID] = deque(maxlen=DEQUEUE_MAX_SIZE)

        self.current_state[ID] = None
        self._tasks_dct[ID] = tasktuple(index, task)
        log.debug(f'Async task (index: {index}, ID: {ID}) created')

    async def _attribute_worker(self, index, ID, attrProxy, devProxy, queue, logged=False, name=None):
        log.debug(f'Worker task ({index} -> {ID}): started')
        await self.startEvent.wait()
        log.debug(f'Worker task ({index}): running')
        last_log = time.time()

        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                await asyncio.sleep(0.5)
                continue

            mess = {
                'index': index,
                'ID': ID,
                'name': name,
                'timestamp': time.time(),
            }

            try:
                mess['value'] = attrProxy.read().value
                mess['state'] = str(devProxy.state()) if devProxy else "UNKNOWN"

                if logged and (time.time() - last_log > LOGTIME):
                    self.log[ID].append(logtuple(time.time(), mess['value']))
                    last_log = time.time()

                self.current_state[ID] = statetuple(mess['value'], str(mess['state']))

            except Exception:
                mess['value'] = None
                mess['state'] = "UNKNOWN"

            await queue.put(mess)
            await asyncio.sleep(self._grace)

        log.debug(f'Worker task ({index} {ID}) stopped')

    async def _start_async(self):
        self.startEvent.set()

    async def _pause_async(self):
        self.pauseEvent.set()

    async def _resume_async(self):
        self.pauseEvent.clear()

    async def _stop_async(self):
        self.stopEvent.set()
        log.debug('Poller tasks stopped')
        for t in self._tasks_dct.values():
            try:
                await t.task
            except asyncio.CancelledError:
                pass

    # ------------------------
    # Context handling helper
    # ------------------------
    def _call_context_aware(self, coro, stop_loop=False):
        """Runs async method in correct context."""
        try:
            loop = asyncio.get_running_loop()
            # Already in async context
            return coro
        except RuntimeError:
            # Sync context
            self._ensure_loop()
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            result = fut.result()
            if stop_loop and self._loop:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._loop_thread.join()
                self._loop = None
                self._loop_thread = None
            return result

    def _ensure_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
            self._loop_thread.start()

DEVDCT = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.2e', 'widgetStyle': 'background'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.2e', 'widgetStyle': 'background'},
        }


async def drain_queue_nonblocking(queue: asyncio.Queue):
    """Drain all currently available items without waiting for more."""
    items = []
    while True:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        else:
            items.append(item)
            queue.task_done()

    if items:
        if VERBOSE:
            print(f"[Thread] Drained {len(items)} items: {items}")
        else:
            print(f"[Thread] Drained {len(items)} items.")

def background_worker(queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
    """Periodically drain the queue from a background thread."""
    while True:
        # Schedule the async drain in the main loop
        fut = asyncio.run_coroutine_threadsafe(
            drain_queue_nonblocking(queue), loop
        )
        fut.result()  # Wait for completion
        # Simulate periodic check
        import time
        time.sleep(1)


async def async_test(queue):
    poller = AsyncPoller(queue)

    print("Setting up Queue drain worker...")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    threading.Thread(target=background_worker, args=(queue, loop), daemon=True).start()

    for k, v in DEVDCT.items():
        await poller.add_attr(v, state=True, name=k)
    await poller.start()
    await asyncio.sleep(5)
    await poller.stop()


def sync_test(queue):
    poller = AsyncPoller(queue)

    print("Setting up Queue drain worker...")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    threading.Thread(target=background_worker, args=(queue, loop), daemon=True).start()

    for k, v in DEVDCT.items():
        poller.add_attr(v, state=True, name=k)
    poller.start()
    time.sleep(5)
    poller.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    queue = asyncio.Queue()

    print("Running AsyncPoller example...")
    try:
        asyncio.run(async_test(queue))
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    
    # This does not work yet. :( 
    # print("Running sync main...")
    # asyncio.run(sync_test(queue))