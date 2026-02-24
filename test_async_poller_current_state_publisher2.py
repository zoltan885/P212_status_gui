
import logging
import sys
import threading
import asyncio
import time



from poller_async import AsyncPoller
from poller_simulator import AsyncSensorSimulator, SENSOR_CONFIG
from current_state_async import CurrentStateMonitorAsync, OverwritingDualModeQueue
from publisher_simple import UpdatePublisher, SnapshotWorker
from database_writer import DatabaseWriter

import importlib
if len(sys.argv) > 1:
    conf_name = sys.argv[1]
    conf = importlib.import_module(conf_name)
    logging.info(f'{sys.argv[1]} imported')
else:
    import configuration as conf

logFormatter = logging.Formatter(
    "%(asctime)-25.25s %(threadName)-12.12s %(name)-25.24s %(levelname)-10.10s %(message)s")
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)

#consoleHandler = logging.StreamHandler(sys.stdout)
#consoleHandler.setFormatter(logFormatter)
#rootLogger.addHandler(consoleHandler)




SIMULATE = True

async def main():
    queue = asyncio.Queue()
    if SIMULATE:
        logging.info("Using AsyncSensorSimulator")
        poller = AsyncSensorSimulator(SENSOR_CONFIG, queue)
    else:
        # Use the actual AsyncPoller if not simulating
        logging.info("Using actual AsyncPoller")
        poller = AsyncPoller(queue = queue)

    update_queue = asyncio.Queue()
    snapshot_queue = asyncio.Queue()# OverwritingDualModeQueue()
    log_queue = asyncio.Queue()
    
    if not SIMULATE:
        for tab in conf.grouping['tabs']:
            for gr in conf.grouping['tabs'][tab].keys():
                for coll in conf.grouping['tabs'][tab][gr]:
                    for k, v in getattr(conf, coll).items():
                        if 'attr' in v.keys():
                            await poller.add_attr(v, state=True, name=k)
    
    await poller.start()
    print("Poller started...")

    CSMA = CurrentStateMonitorAsync(
        in_queue=queue, 
        update_queue=update_queue, 
        snapshot_queue=snapshot_queue,
        log_queue=log_queue
    )

    publisher = UpdatePublisher(update_queue, topic="sensors.updates")
    await publisher.setup()
    publisher.publish_time_constant = 0.3
    publisher.publish_event.set()

    snapshot_worker = SnapshotWorker(snapshot_queue, topic="sensors.snapshot", request_topic="sensors.snapshot.request")
    await snapshot_worker.setup()
    snapshot_worker.publish_periodic = True


    CSMA.snapshot_interval = 5
    CSMA.update_interval = 0.1
    print("Starting CurrentStateMonitorAsync...")
    await CSMA.start_update()
    #await CSMA.start_snapshot()
    print("CurrentStateMonitorAsync started...")

    # DBW = DatabaseWriter(in_queue=log_queue)
    # print("DatabaseWriter starting...")
    # await DBW.run()
    
    sleep_time = 50000
    print(f"Sleeping for {sleep_time} seconds...")
    await asyncio.sleep(sleep_time/2)
    # print('\nON DEMAND SNAPSHOT')
    # await CSMA.snapshot()
    # print('\n')
    await asyncio.sleep(sleep_time/2)
    print("Stopping CurrentStateMonitorAsync...")
    try:
        await CSMA.stop_update()
        await CSMA.stop_snapshot()
    except Exception as e:
        pass
    print("CurrentStateMonitorAsync stopped...")
    print('Getting a snapshot...')
    await CSMA.snapshot()

    print("Stopping poller...")
    await poller.stop() 
    print("Poller stopped...")
    print("All tasks completed, exiting...")

if __name__ == "__main__":  
    logging.basicConfig(level=logging.DEBUG)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, stopping...")
    except Exception as e:
        logging.error(f"An error occurred: {e}")



