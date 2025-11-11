# tine_poller.py

#!/usr/bin/env python3
import logging
import sys
import PyTine as tine
import asyncio
import threading
from enum import Enum

from base_classes import AsyncPoller, TineAddress, TineGroup, TineGroupCollection
import utilities
import time
from registry import Sensor, SensorRegistry

logger = logging.getLogger(__name__)
#logger.setLevel(logging.INFO)

GRACE = 1  # seconds
TEST = False

class AsyncTinePoller():
    def __init__(self, outqueue: asyncio.Queue, registry: SensorRegistry):
        self.startEvent = asyncio.Event()
        self.pauseEvent = asyncio.Event()
        self.stopEvent = asyncio.Event()
        self.startEvent.clear()
        self.pauseEvent.clear()
        self.stopEvent.clear()

        self.queue = outqueue

        self.registry = registry
        self.registry_notification_queue = registry.subscribe()  # this is not yet used
        self.tasks = {}
        self._grace = GRACE

        self._loop = None
        self._loop_thread = None

        self._add_all_registry_entries()

        if TEST:
            task = asyncio.create_task(
                    self.queue_consumer(self.queue)
                )
            

    # ------------------------
    # Public methods (context-aware)
    # ------------------------

    def start(self):
        return self._call_context_aware(self._start_async())

    def pause(self):
        return self._call_context_aware(self._pause_async())

    def resume(self):
        return self._call_context_aware(self._resume_async())

    def stop(self):
        self.registry.unsubscribe(self.registry_notification_queue)
        return self._call_context_aware(self._stop_async(), stop_loop=True)
    
    async def _start_async(self):
        self.startEvent.set()
        self.pauseEvent.clear()  # could be used for resuming

    async def _pause_async(self):
        self.pauseEvent.set()

    async def _resume_async(self):
        self.pauseEvent.clear()

    async def _stop_async(self):
        self.stopEvent.set()
        logger.debug('Poller stopping...')
        for task in list(self.tasks.values()):
            if not task.done():
                logger.debug(f'Cancelling task {task}')
                task.cancel()
        
        # Gather all tasks, handling cancellations and exceptions
        done, pending = await asyncio.wait(self.tasks.values(), return_when=asyncio.FIRST_EXCEPTION)

        # Handle the exceptions and cancellations for each task
        for task in done:
            if task.exception():
                logger.error(f"Task {task} raised an exception: {task.exception()}")
            elif task.cancelled():
                logger.debug(f"Task {task} was cancelled.")
        
        #await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()
        logger.debug('All tasks stopped.')

    # ------------------------
    # Async core methods
    # ------------------------
    
    def _add_all_registry_entries(self,):
        '''
        adds all registered Tine addresses from the SensorRegistry to the polling group
        takes care of starting the process if it is not running yet
        Modifying the registry while polling is ongoing is not yet handled. The notification queue is created, but not yet used.
        '''
        logger.info('Adding all Tine addresses from registry to poller')
        logger.debug(f'Current tine groups in registry: {self.registry.tine_groups}')
        for tine_group_ID, sensor_ID_list in self.registry.tine_groups.items():
            logger.debug(f'Processing tine_group_ID: {tine_group_ID} with sensors: {sensor_ID_list}')
            if tine_group_ID in self.tasks:
                logger.info(f'Task with tine_group_ID {tine_group_ID} already exists')
                continue
            task = asyncio.create_task(
                self.query_process(sensor_ID_list)
            )
            self.tasks[tine_group_ID] = task
            logger.info(f'Created polling task for {tine_group_ID=}')
        logger.debug(f'Total polling tasks: {len(self.tasks)}')


    async def query_process(self, sensor_ID_list: list[str]):
        logger.debug(f'Starting query_process for sensor_ID_list: {sensor_ID_list}')
        # determine context/server/property from the first sensor ID
        sensor = self.registry.get_sensor_by_id(sensor_ID_list[0])
        context, server, property = getattr(sensor, 'context'), getattr(sensor, 'server'), getattr(sensor, 'property')
        # get the name of all devices in this tine group
        dev_names_to_query = [getattr(self.registry.get_sensor_by_id(sid), 'device') for sid in sensor_ID_list]
        # get all devices belonging to the group on the TINE SERVER
        all_devs_in_tine = tine.list(context=context, server=server, property=property)['devices']
        _first_device = all_devs_in_tine[0]  # this is to query tine.get
        # get the indices of all devices to be queried
        idxs = [all_devs_in_tine.index(d) for d in dev_names_to_query if d in all_devs_in_tine]
        sensor_ID_list_idx_map = {ID: idx for ID,idx in zip(sensor_ID_list, idxs)}
        logger.debug(f'Polling TINE server for {context}/{server}/{property} for devices: {dev_names_to_query}')

        # start the polling loop
        while not self.stopEvent.is_set():
            try:
                if self.pauseEvent.is_set():
                    await asyncio.sleep(0.1)
                    continue
                logger.debug(f'Polling TINE server for {context}/{server}/{property} for devices: {dev_names_to_query}')
                try:
                    all_values_from_tine_server = await asyncio.get_event_loop().run_in_executor(None, tine.get, f'{context}/{server}/{_first_device}', property)
                except Exception as e:
                    logger.error(f"Error querying TINE server for {context}/{server}/{property}: {e}")
                    await asyncio.sleep(self._grace)
                    continue
                for sID, idx in sensor_ID_list_idx_map.items():
                    dct = {
                        'name': f'{context}/{server}/{self.registry.get_sensor_by_id(sID).device}',  # this field is for easier identification, should be redundant
                        'ID': sID,
                        'timestamp': all_values_from_tine_server['timestamp'],
                        'value': all_values_from_tine_server['data'][idx],
                        'state': all_values_from_tine_server['status'],
                    }
                    await self.queue.put(dct)
                await asyncio.sleep(self._grace)
            except asyncio.CancelledError:
                logger.debug(f'query_process for sensor_ID_list {sensor_ID_list} cancelled.')
                raise



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

    async def queue_consumer(self, queue: asyncio.Queue):
        while True:
            msg = await queue.get()
            print(f"Queue Consumer received:\n{msg}")
            queue.task_done()    




async def queue_consumer(queue: asyncio.Queue):
    while True:
        msg = await queue.get()
        logging.info(f"Queue Consumer received:\n{msg}")
        queue.task_done()


sensors = [
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/PU21b',
        'property': 'Undulator.Gap',
        'display_name': 'PU21b Gap'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/PU07',
        'property': 'Undulator.Gap',
        'display_name': 'PU07 Gap'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/P1max',
        'property': 'P21.Druck',
        'display_name': 'P1max Pressure'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/ITR_Mono_B',
        'property': 'P21.Druck',
        'display_name': 'P2max Pressure'
    },

]


async def async_main():
    registry = SensorRegistry()
    outqueue = asyncio.Queue()
    asyncio.create_task(queue_consumer(outqueue))
    
    await registry.register_many(sensors) 
    logging.debug(f'Registry sensors: {registry.get_all()}')
    logging.debug(f'Registry tine groups: {registry.tine_groups}')

    poller = AsyncTinePoller(outqueue, registry)

    await poller.start()
    await asyncio.sleep(5)  # Run for 5 seconds for testing
    await poller.pause()
    logging.info('Poller paused for 5 seconds') 
    await asyncio.sleep(5)
    await poller.resume()
    logging.info('Poller resumed for another 5 seconds')
    await asyncio.sleep(5)
    await poller.stop()
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    asyncio.run(async_main())