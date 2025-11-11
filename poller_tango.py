#!/usr/bin/env python3

import logging
import sys
import tango
import asyncio
import threading
from typing import List
from datetime import datetime, timezone

from base_classes import AsyncPoller
import utilities
import time
from registry import Sensor, SensorRegistry

logger = logging.getLogger(__name__)
#logger.setLevel(logging.INFO)

GRACE = 1  # seconds
TEST = False

# Configuration
MAX_GLOBAL_CONCURRENCY = 20
DEFAULT_POLL_INTERVAL = 0.2  # seconds
SLOW_DEVICE_THRESHOLD = 0.5  # seconds, device considered slow if read takes longer
MAX_BACKOFF = 5.0  # maximum poll interval for slow devices



class AsyncTangoPoller():
    def __init__(self, outqueue: asyncio.Queue, registry: SensorRegistry):
        self.startEvent = asyncio.Event()
        self.pauseEvent = asyncio.Event()
        self.stopEvent = asyncio.Event()
        self.startEvent.clear()
        self.pauseEvent.clear()
        self.stopEvent.clear()

        self.outqueue = outqueue
        self.semaphore = asyncio.BoundedSemaphore(MAX_GLOBAL_CONCURRENCY)

        self.registry = registry
        self.registry_notification_queue = registry.subscribe()  # this is not yet used
        self.tasks = {}
        self._grace = GRACE

        self._loop = None
        self._loop_thread = None

        self._add_all_registry_entries()

        if TEST:
            task = asyncio.create_task(
                    self.queue_consumer(self.outqueue)
                )
            

    # ------------------------
    # Public methods (context-aware)
    # ------------------------

    def start(self):
        """
        Start the tango poller.
        """
        return self._call_context_aware(self._start_async())

    def pause(self):
        """
        Pause the poller.
        """
        return self._call_context_aware(self._pause_async())

    def resume(self):
        """
        Resume polling operations.
        """
        return self._call_context_aware(self._resume_async())

    def stop(self):
        """
        Stop the poller and perform shutdown/cleanup.
        """
        self.registry.unsubscribe(self.registry_notification_queue)
        return self._call_context_aware(self._stop_async(), stop_loop=True)
    
    async def _start_async(self):
        """
        Start the asynchronous poller by signaling the start event and clearing the pause event.
        """
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
        adds all registered Tango addresses from the SensorRegistry to the polling group
        takes care of starting the process if not running yet
        Modifying the registry while polling is not yet handled. The notification queue is created, but not yet used.
        '''
        logger.info('Adding all Tango addresses from registry to poller')
        logger.debug(f'Current Tango groups in registry: {self.registry.tango_groups}')
        for tango_group_address, sensor_ID_list in self.registry.tango_groups.items():
            logger.debug(f'Processing {tango_group_address=} with sensors: {sensor_ID_list}')
            if tango_group_address in self.tasks:
                logger.info(f'Task with {tango_group_address=} already exists')
                continue
            else:
                logger.info(f'Creating polling task for {tango_group_address=}')
                attrs = self.registry.get_tango_group_attributes(tango_group_address)
                task = asyncio.create_task(
                    #self.query_process(tango_group_address, attrs)
                    self.query_process(sensor_ID_list)
                )
                self.tasks[tango_group_address] = task
                logger.info(f'Created polling task for {tango_group_address=}')
        logger.debug(f'Total polling tasks: {len(self.tasks)}')

    ###################################
    async def read_attrsA(self, dev: tango.DeviceProxy, attrs: List[str]):
        """
        Read Tango attributes with global concurrency limit.
        """
        if not 'State' in attrs:  # this is to query the device state as well
            attrs.append('State')
        async with self.semaphore:
            loop = asyncio.get_running_loop()
            start = time.time()
            try:
                result = await loop.run_in_executor(None, dev.read_attributes, attrs)
            except Exception as e:
                print(f"Error reading attributes from {dev.name()}: {e}")
                return None, 0.0
            duration = time.time() - start
            return result, duration

    def _timeval_to_unix(self, tv):
        """
        Convert a timeval structure to Unix timestamp (seconds since epoch).
        """
        sec = tv.tv_sec
        if hasattr(tv, "tv_usec") and tv.tv_usec:
            return sec + tv.tv_usec / 1_000_000.0
        if hasattr(tv, "tv_nsec") and tv.tv_nsec:
            return sec + tv.tv_nsec / 1_000_000_000.0
        return float(sec)
    
    def _timeval_to_datetime(self, tv):
        """
        Convert a timeval-like object to an aware UTC datetime.
        """
        ts = self._timeval_to_unix(tv)
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    async def query_process(self, sensor_ID_list: list[str]):
        """
        Asynchronously poll a Tango device for attribute values at regular intervals.
        """
        sensor = self.registry.get_sensor_by_id(sensor_ID_list[0])
        address = sensor.address
        dev = tango.DeviceProxy(sensor.address)
        # get the attributes to be polled
        attrs = {}
        for sID in sensor_ID_list:
            s = self.registry.get_sensor_by_id(sID)
            attrs[s.attribute] = sID
        logging.debug(f'Starting polling for Tango device {address} with attributes {attrs}')
        interval = DEFAULT_POLL_INTERVAL
        await self.startEvent.wait()
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                await asyncio.sleep(0.1)
                continue
            try:
                result, duration = await self.read_attrsA(dev, list(attrs.keys()))
                if result is None:
                    # Read failed, apply backoff
                    interval = min(MAX_BACKOFF, interval * 2)
                    await asyncio.sleep(interval)
                    continue
                state = 'Unknown'
                if 'State' in [attr.name for attr in result]:
                    state = [av.value for av in result if av.name == 'State'][0]
                    state = str(state)
                    #state_attr = getattr(result, 'State', 'Unknown')
                    #state = str(state_attr)
                    #logger.warning(f"Device {address} state: {state}")
                for attr in result:
                    # await self.outqueue.put({
                    #     "device": address,
                    #     "attr": attr.name,
                    #     "value": attr.value,
                    #     "timestamp": self._timeval_to_unix(attr.time)
                    # })
                    await self.outqueue.put({
                        'name': f'{address}/{attr.name}',  # this field is for easier identification, should be redundant
                        'ID': attrs[attr.name],
                        'timestamp': self._timeval_to_unix(attr.time),
                        'value': attr.value,
                        'state': state,
                    })

                # Dynamic adjustment of poll interval based on response time
                if duration > SLOW_DEVICE_THRESHOLD:
                    interval = min(MAX_BACKOFF, interval * 1.5)  # backoff for slow devices
                else:
                    interval = DEFAULT_POLL_INTERVAL
                logging.debug(f'Interval adjusted to {interval} seconds based on response time {duration} seconds')

            except tango.DevFailed as e:
                print(f"[{address}] Tango error: {e}")
                interval = min(MAX_BACKOFF, interval * 2)  # exponential backoff on errors

            await asyncio.sleep(interval)

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
import itertools
attrs_VME = ['Acceleration', 'BaseRate', 'Conversion', 'SettleTime', 'SlewRate', 'SlewRateMax', 'SlewRateMin', 'StepBacklash', \
            'UnitBacklash', 'UnitCalibration', 'UnitLimitMax', 'UnitLimitMin', 'CwLimit', 'CcwLimit', 'Position', 'AccuLimitMin',\
            'ConversionEncoder', 'PositionEncoder', 'Status']  # 19 attributes

sensors2 = [{'type': 'Tango',
        'address': f'hasep21eh2:10000/p21/motor/eh2_u1.{d:02d}',
        'attribute': attr,
        'display_name': f'eh2_u1.{d:02d} Position'
    } for d in range(1, 2) for attr in attrs_VME]



# attrs_ZMX = ['StopCurrent', 'RunCurrent', 'PreferentialDirection', 'StepWidth', 'DelayTime', 'StepWidthStr', \
#             'Temperature', 'IntermediateVoltage', 'Channel_rd', 'AxisName', 'InputLogicLevel', 'Deactivation',\
#             'Overdrive', 'OperationMode', 'DeactivationStr', 'PreferentialDirectionStr', 'InputLogicLevelStr', \
#             'OverdriveStr', 'State', 'Status'] # 20 attributes
# devices: Dict[str, List[str]] = {**{f'hasep21eh2:10000/p21/motor/eh2_u1.{d:02d}': attrs_VME for d in range(1, 17)},
#                                 **{f'hasep21eh2:10000/p21/motor/eh2_u2.{d:02d}': attrs_VME for d in range(1, 17)},\
#                                 **{f'hasep21eh2:10000/p21/ZMX/eh2_u1.{d:02d}': attrs_ZMX for d in range(1, 17)},\
#                                 **{f'hasep21eh2:10000/p21/ZMX/eh2_u2.{d:02d}': attrs_ZMX for d in range(1, 17)}\
#                                 }



async def async_main():
    registry = SensorRegistry()
    outqueue = asyncio.Queue()
    asyncio.create_task(queue_consumer(outqueue))
    
    await registry.register_many(sensors)
    await registry.register_many(sensors2) 
    logging.warning(f'Registry sensors: {registry.get_all()}')

    logging.debug(f'Registry tine groups: {registry.tine_groups}')

    poller = AsyncTangoPoller(outqueue, registry)

    await poller.start()
    await asyncio.sleep(10)  # Run for 5 seconds for testing
    await poller.pause()
    logging.info('Poller paused for 5 seconds') 
    await asyncio.sleep(5)
    await poller.resume()
    logging.info('Poller resumed for another 5 seconds')
    await asyncio.sleep(10)
    await poller.stop()
    

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    asyncio.run(async_main())