

import asyncio
import logging
from base_classes import TineAddress, TineGroup, TineGroupCollection
from tine import AsyncTinePoller
from poller_async import AsyncPoller
from QueueMerger import QueueMerger
from sensor_registry import SensorRegistry

logger = logging.getLogger(__name__)
GRACE = 1  # seconds
TEST = True

async def queue_consumer(queue: asyncio.Queue):
    while True:
        msg = await queue.get()
        print(f"Queue Consumer received:\n{msg}")
        queue.task_done()

async def main():
    tine_queue = asyncio.Queue()
    tango_queue = asyncio.Queue()
    registry = SensorRegistry()

    Merger = QueueMerger()
    await Merger.add_queue("Tine", tine_queue)
    await Merger.add_queue("Tango", tango_queue)
    merged_queue = Merger.get_output_queue()
    task = asyncio.create_task(
                    queue_consumer(merged_queue)
                )

    ATP = AsyncTinePoller(tine_queue)
    Tine_entries = [
        TineAddress("PETRA", "HISTORY", "PS2_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "P1max", "P21.Druck"),
        TineAddress("PETRA", "HISTORY", "V2_B", "P21.Stellung"),
        TineAddress("PETRA", "HISTORY", "ITR_Mono_B", "P21.Druck"),
    ]

    for ta in Tine_entries:
        ta.add_id(registry.register_sensor({'type': 'Tine',
                                           'address': f'{ta.server}/{ta.context}/{ta.device}',
                                           'display_name': f'{ta.device} {ta.property}',
                                           'property': ta.property,
                                           'additional_fileds1': 'value1',
                                           'additional_field2': 'value2',
                                           }))

    await ATP.add_entry(Tine_entries)
    print(registry.all_sensors())

    AP = AsyncPoller(tango_queue)
    DEVDCT = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.2e', 'widgetStyle': 'background'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.2e', 'widgetStyle': 'background'},
        }
    #AP.add_devices(DEVDCT)

    for k, v in DEVDCT.items():
        await AP.add_attr(v, state=True, name=k)
    
    
    await ATP.start()
    await AP.start()

    await asyncio.sleep(10)
    

if __name__ == "__main__":
    asyncio.run(main())

