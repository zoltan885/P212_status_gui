#test_registry_tine_async_poller

import asyncio
from registry import SensorRegistry
from tine import AsyncTinePoller

ADDRS = [{'type': 'Tine', 'address': 'PETRA/HISTORY/PU21b', 'property': 'Undulator.Gap', 'display_name': 'PU21b Gap'},
         ]


async def queue_consumer(queue: asyncio.Queue):
    while True:
        msg = await queue.get()
        print(f"Queue Consumer received:\n{msg}")
        queue.task_done()

async def main():
    registry = SensorRegistry()
    for addr in ADDRS:
        A = await registry.register_sensor(addr)
        print(f'Sensor registered: {A}')

    print(f'Sensors in registry: {registry.get_all()}')

    outqueue = asyncio.Queue()
    asyncio.create_task(queue_consumer(outqueue))

    poller = AsyncTinePoller(outqueue=outqueue, registry=registry)
    await poller.start()
    #await asyncio.sleep(5)  # Run for 10 seconds for testing
    #await poller.stop()

if __name__ == "__main__":
    asyncio.run(main())