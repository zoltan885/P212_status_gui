# statusGIU.py
#!/usr/bin/env python3

# this file is intended for continuous testing of the different modules


from registry import SensorRegistry
import asyncio
from poller_tine import AsyncTinePoller
from poller_tango import AsyncTangoPoller
from queue_merger import QueueMerger
from current_state_async import CurrentStateMonitorAsync
from utilities import queue_consumer

from sensors_for_testing import tango_sensors, tine_sensors

import logging

async def main():
    registry = SensorRegistry()
    await registry.register_many(tango_sensors)
    await registry.register_many(tine_sensors)
    #print(f"Registered sensors: {registry.get_all()}")

    outqueue_tango = asyncio.Queue()
    outqueue_tine = asyncio.Queue()

    tango_poller = AsyncTangoPoller(outqueue_tango, registry)
    tine_poller = AsyncTinePoller(outqueue_tine, registry)

    merger = QueueMerger()
    await merger.add_queue('tango', outqueue_tango)
    await merger.add_queue('tine', outqueue_tine)

    merged_queue = merger.get_output_queue()

    update_queue = asyncio.Queue()
    snapshot_queue = asyncio.LifoQueue()
    state_monitor = CurrentStateMonitorAsync(merged_queue, update_queue, snapshot_queue)

    await state_monitor.start_update()

    asyncio.create_task(queue_consumer(update_queue))

    await tango_poller.start()
    await tine_poller.start()

    await asyncio.sleep(15)  # Run for 10 seconds for testing
    await tango_poller.stop()
    await tine_poller.stop()
    await merger.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    asyncio.run(main())