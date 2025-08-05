#!/usr/bin/env python3
# -*- coding: utf-8 -*-



import logging
import time
import os
import sys
from queue import Queue, Empty
import threading
import asyncio
import json
import time
import gzip
import base64
import nkeys
from nats.aio.client import Client as NATS

from load_credits import parse_creds
from poller import Poller
from current_state import CurrentStateMonitor
#from status_bar import Ui_Widget  # this should be changed

import importlib
if len(sys.argv) > 1:
    conf_name = sys.argv[1]
    conf = importlib.import_module(conf_name)
    logging.info(f'{sys.argv[1]} imported')
else:
    import configuration as conf

VERSION = {'major': 1, 'minor': 2, 'patch': 0}

logFormatter = logging.Formatter(
    "%(asctime)-25.25s %(threadName)-12.12s %(name)-25.24s %(levelname)-10.10s %(message)s")
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)
# logging.getLogger().setLevel(logging.DEBUG)
fileHandler = logging.FileHandler(os.path.join(os.getcwd(), 'server_client_test.log'))
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)


_coolBlue = '#0d6efd'

CRED_PATH = "/home/p212user/zoltan/P212_status_gui/credits.creds"
USE_GZIP = True  # Set to True to enable gzip compression
PUBLSIH_SNAPSHOT = False  # Set to True to publish full snapshot on startup

def encode_data(data: dict, use_gzip: bool) -> bytes:
    bytedata = json.dumps(data).encode("utf-8")
    if use_gzip:
        return gzip.compress(bytedata)
    else:
        return bytedata

# async def send_incremental_update(nc, update):
#     await nc.publish("sensors.updates", encode_data(update, USE_GZIP))

async def snapshot_request_handler(connection, msg, snapshot):
    """
    Respond to snapshot requests with the current full snapshot.
    """
    reply = msg.reply
    if reply:
        # Serialize full snapshot to JSON
        snapshot_json = json.dumps(snapshot).encode()
        await connection.publish(reply, snapshot_json)
        print(f"Sent snapshot response to {reply}")

async def periodic_snapshot_publisher(jetstream, snapshot):
    """
    Optional: periodically publish full snapshots on JetStream for history.
    """
    while True:
        snapshot_json = json.dumps(snapshot).encode()
        await jetstream.publish("sensors.state", snapshot_json)
        print("Published full snapshot to sensors.state")
        await asyncio.sleep(60)  # every 60 seconds


def queue_printer(queue):
    """
    Prints the contents of a queue to the console.
    """
    while True:
        try:
            item = queue.get(timeout=0.1)
            print('>>>>>>', item)
        except Empty:
            continue
        except Exception as e:
            logging.error(f"Error printing queue: {e}")
            break

def monitor_queue(queue, interval=1.0):
    while True:
        t0 = time.time()
        print(f"Queue size: {queue.qsize()}")
        while time.time() - t0 < interval:
            time.sleep(0.001)


PUBLISH = True  # Set to True to enable publishing updates
MONITOR = False

async def main():
    comm_queue = Queue(20000)
    poller = Poller(queue = comm_queue)

    update_queue = Queue(1000)
    snapshot_queue = Queue(2)
    
    
    for tab in conf.grouping['tabs']:
        for gr in conf.grouping['tabs'][tab].keys():
            for coll in conf.grouping['tabs'][tab][gr]:
                for k, v in getattr(conf, coll).items():
                    if 'attr' in v.keys():
                        poller.add_attr(v, state=True, name=k)
    poller.start()
    
    if MONITOR:
        monitor_thread = threading.Thread(target=monitor_queue, args=(comm_queue,), daemon=True)
        monitor_thread.start()

    CSM = CurrentStateMonitor(in_queue=comm_queue, update_queue=update_queue, snapshot_queue=snapshot_queue)
    CSM.start_self_report()
    
    if PUBLISH:
        jwt, seed = parse_creds(CRED_PATH)
        kp = nkeys.from_seed(seed.encode())
        nc = NATS()
        

        await nc.connect(
            servers=["tls://connect.ngs.global:4222"],
            user_jwt_cb=lambda: jwt.encode("utf-8"),
            signature_cb=lambda nonce: base64.b64encode(kp.sign(nonce.encode())),
            name="jwt-python-publisher",
        )

        #js = nc.jetstream()
        #await nc.subscribe("sensors.snapshot.request", cb=snapshot_request_handler)

    if PUBLISH:
        await nc.publish("sensors.updates", encode_data({1: {1: 'Greetings', 'timestamp': time.time()}}, USE_GZIP))
    c = 0
    while True:
        try:
            if PUBLISH:
                logging.debug('Publishing updates...')
                #dct = {'dict': {'value': 12345, 'timestamp': time.time()}}  
                dct = {}
                ctr = 1
                if not update_queue.empty():
                    logging.debug(f'Queue size: {update_queue.qsize()}')
                    while not update_queue.empty():
                        dct[ctr] = update_queue.get(timeout=0.1)
                        ctr += 1
                if dct:
                    await nc.publish("sensors.updates", encode_data(dct, USE_GZIP))
                    #logging.warning(f"Published update: {dct}")
            else:
                queue_printer(queue=update_queue)
                
        except asyncio.CancelledError:
            logging.info("KeyboardInterrupt received, exiting...")
            break
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            break
        finally:
            if MONITOR:
                monitor_thread.join(timeout=0.1)

        await asyncio.sleep(0.1)  # Adjust sleep time as needed
        c += 1
        logging.debug(f'End of loop: {c}')

    poller.stop()




if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, exiting...")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        logging.info("Exiting main program.")
        sys.exit(0)
