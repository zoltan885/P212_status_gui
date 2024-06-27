#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 18 20:47:13 2024

@author: hegedues
"""


import utilities
import conditions
import numpy as np
import time
import os
from collections import namedtuple, deque, defaultdict
import requests
# import asyncio
# import aiohttp
import zmq

from threading import Thread
from multiprocessing import Event, Process, Pool  # , Queue
from queue import Queue
import subprocess
import logging
log = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)  # This supresses the urllib3 debug messages

try:
    import PyTango as PT
    TANGO = True
except ImportError as e:
    log.warning(f"{e}")

TINEBASEADDRESS = 'http://acclxcisrv03.desy.de:8080/TINE_Restful/PETRA/HISTORY/'

GRACE = 2
DEQUEUE_MAX_SIZE = 2000
logtuple = namedtuple('log', ['time', 'value'])
threadtuple = namedtuple('thread', ['index', 'thread'])
statetuple = namedtuple('state', ['value', 'state'])

TINE_STATE_LIKE_PROPS = ['P21.Stellung']

TINE_STATE_COLORS = {'0': 'UNKNOWN', '1': 'ALARM', '2': 'ON'}
TINE_STATE_TEXT = {'0': 'UNKNOWN', '1': 'CLOSED', '2': 'OPEN'}


'''
One can request all devices with P21.Stellung property by omitting the device from the query url:
    http://acclxcisrv03.desy.de:8080/TINE_Restful/PETRA/HISTORY//P21.Stellung/?content=JSON
    
    [{"name":"VServ","context":"PETRA","server":"HISTORY"},{"name":"LM0_A","context":"PETRA","server":"HISTORY"},{"name":"PS0_A","context":"PETRA","server":"HISTORY"},{"name":"V0_A","context":"PETRA","server":"HISTORY"},{"name":"LS0_A","context":"PETRA","server":"HISTORY"},{"name":"LM1_A","context":"PETRA","server":"HISTORY"},{"name":"PS1_A","context":"PETRA","server":"HISTORY"},{"name":"PS2_A","context":"PETRA","server":"HISTORY"},{"name":"FI0_A","context":"PETRA","server":"HISTORY"},{"name":"FI1_A","context":"PETRA","server":"HISTORY"},{"name":"FI2LM2_A","context":"PETRA","server":"HISTORY"},{"name":"LM3_A","context":"PETRA","server":"HISTORY"},{"name":"OAbs_A","context":"PETRA","server":"HISTORY"},{"name":"BS0_A","context":"PETRA","server":"HISTORY"},{"name":"LM0_B","context":"PETRA","server":"HISTORY"},{"name":"PS0_B","context":"PETRA","server":"HISTORY"},{"name":"V0_B","context":"PETRA","server":"HISTORY"},{"name":"LS0_B","context":"PETRA","server":"HISTORY"},{"name":"LM1_B","context":"PETRA","server":"HISTORY"},{"name":"PS1_B","context":"PETRA","server":"HISTORY"},{"name":"PS2_B","context":"PETRA","server":"HISTORY"},{"name":"FI0_B","context":"PETRA","server":"HISTORY"},{"name":"FI1_B","context":"PETRA","server":"HISTORY"},{"name":"FI2LM2_B","context":"PETRA","server":"HISTORY"},{"name":"LM3_B","context":"PETRA","server":"HISTORY"},{"name":"OAbs_B","context":"PETRA","server":"HISTORY"},{"name":"BS0_B","context":"PETRA","server":"HISTORY"},{"name":"LM5_A","context":"PETRA","server":"HISTORY"},{"name":"BS1_A","context":"PETRA","server":"HISTORY"},{"name":"BS2_A","context":"PETRA","server":"HISTORY"},{"name":"V2_B","context":"PETRA","server":"HISTORY"},{"name":"V3_B","context":"PETRA","server":"HISTORY"},{"name":"LM5_B","context":"PETRA","server":"HISTORY"},{"name":"BS1_B","context":"PETRA","server":"HISTORY"},{"name":"BS2_B","context":"PETRA","server":"HISTORY"},{"name":"BS3_B","context":"PETRA","server":"HISTORY"}]

then by querying the first element in this list, one gets all current values in a list, that might be 
longer than the actual device list !!!

    http://acclxcisrv03.desy.de:8080/TINE_Restful/PETRA/HISTORY/VServ/P21.Stellung/?content=JSON

This way we just need an collector for all Tine devices with the same property we want to query and put them into a single request
E.g. all valve and shutter devices could be queried with a single request to the P21.Stellung property, but we'd need to know the meaning of the list elements.
One would still need multiple requests for mutliple properties

The approach would work the other way around as well (list the properties belonging to one device),
but this tends to result in much bigger arrays

'''


class TinePoller():
    '''
    Class aimed at polling tine device properties in a smart way

    Devices are gatered in property groups, beacuse all devices with 
    the same property may be requested with a single api call

    The dict loggedProperties contains all information about the properties 
    and devices the current object is aware of.

    The number of currently logged Tine devices can be checked with the 
    number_of_logged_devices property of the current object

    Each property has its own worker thread, i.e. the object runs as many 
    threads as individual properties, not as individual devices
    '''

    def __init__(self, ):
        self.startEvent = Event()
        self.pauseEvent = Event()
        self.stopEvent = Event()
        self.queue = Queue(20000)
        self._loggedProperties = defaultdict(dict)
        # {
        # prop1: {full_dev_list: [], current_devices: {dev1: index, dev2: index}},
        # prop2: {full_dev_list: [], current_devices: {dev1: index, dev2: index}},
        # } index: of the dev in the tine list
        self._threads_dct = {}
        self.log = {}
        self.current_state = {}  # dict holding the current state (meant for external appl)
        self._grace = GRACE  # this could then be set externally

        self.start()

    def _categorize(self, tineaddr):
        pass

    def _get_new_prop_list(self, tineaddr: str):
        '''
        This function gets called when a new Tine property is added to the logged list
        It extends the loggedProperties dictionary and starts a new worker for the new property
        '''
        print('get new prop list')
        prop = tineaddr['tine_property']
        # http://acclxcisrv03.desy.de:8080/TINE_Restful/PETRA/HISTORY//P21.Stellung/?content=JSON
        url = TINEBASEADDRESS + f'/{prop}/?content=JSON'
        try:
            resp = requests.get(url, timeout=(0.2, 0.2))
            dev_list = [i['name'] for i in resp.json()]
            if len(dev_list) == 1 and dev_list[0] == 'keyword':
                log.error(f'No such Tine property: {prop}')
                raise IOError
        except:
            log.error(f'No such Tine property: {prop}')
        self._loggedProperties[prop]['full_dev_list'] = dev_list
        self._loggedProperties[prop]['current_devices'] = {}
        log.info(f'full_dev_list created for property {prop}')
        # starting new thread
        ind = self.running_threads
        thr = Thread(target=self._tine_worker, args=(), kwargs={'tineaddr': tineaddr,
                                                                'thread_index': ind,
                                                                'queue': self.queue,
                                                                })
        thr.start()
        self._threads_dct[prop] = thr

    def _add_dev_to_log(self, tineaddr):
        prop = tineaddr['tine_property']
        dev = tineaddr['tine_dev']
        if prop not in self._loggedProperties.keys():
            self._get_new_prop_list(tineaddr)
        if dev not in self._loggedProperties[prop]['full_dev_list']:
            log.error(f'{dev} not in full device list of {prop}\ndevice not added to logging')
        ind = self._loggedProperties[prop]['full_dev_list'].index(dev)
        if dev in self._loggedProperties[prop]['current_devices'].keys():
            log.info(f'Tine device {dev} already in the list under {prop}, nothing to do')
            # print('Was already there')
            return
        self._loggedProperties[prop]['current_devices'][dev] = ind
        log.info(f'Device {dev} added to logging under {prop}')
        log.info(self.loggedProperties)

    def _tine_worker(self, tineaddr: str, thread_index: int, queue: Queue):
        tine_property = tineaddr['tine_property']
        log.debug(f'Tine worker thread ({thread_index} -> {tine_property}): started')
        self.startEvent.wait()
        dev_to_poll = self._loggedProperties[tine_property]['full_dev_list'][0]
        log.debug(f'Tine worker thread ({thread_index} -> {tine_property}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            current_devices = self._loggedProperties[tine_property]['current_devices']
            print(f'Current devices: {current_devices}')
            success = False
            try:
                url = TINEBASEADDRESS + dev_to_poll + '/' + tine_property + '/?content=JSON'
                # log.debug(f'URL: {url}')
                resp = requests.get(url, timeout=(0.2, 0.2))
                # log.debug(f'RESPONSE: {resp.json()}')
                last_state = resp.json()['data']
                success = True
            except:
                pass
            if success:
                for dev, index in current_devices.items():
                    mess = {}
                    mess['index'] = thread_index
                    ID = f"tine::{dev}/{tine_property}"
                    mess['ID'] = ID
                    mess['state'] = 'UNKNOWN'
                    if tine_property in TINE_STATE_LIKE_PROPS:
                        mess['value'] = TINE_STATE_TEXT[last_state[index]]
                        self.current_state[ID] = statetuple(mess['value'], str(mess['state']))
                        mess['state'] = TINE_STATE_COLORS[str(last_state[index])]
                    else:
                        mess['value'] = last_state[index]
                        self.current_state[ID] = statetuple(mess['value'], str(mess['state']))
                        mess['state'] = 'ON'
                    queue.put(mess)
                    log.debug(f'Message put in queue ({self.queue}): {mess}')
            # this is for the thread to quickly terminate
            t = time.time()
            while not self.stopEvent.is_set() and time.time()-t < self._grace:
                time.sleep(0.01)
        log.debug(f'Worker thread ({thread_index}: Tine {tine_property}) stopped')

    @property
    def loggedProperties(self):
        return self._loggedProperties

    @property
    def number_of_logged_devices(self):
        lst = [len(dl['current_devices']) for dl in self._loggedProperties.values()]
        return sum(lst)

    @property
    def number_of_properties(self):
        return len(list(self._loggedProperties.keys()))

    @property
    def running_threads(self):
        return len(list(self._threads_dct.keys()))

    #
    #
    def start(self):
        self.startEvent.set()
        log.debug('Tine poller threads started')

    def pause(self):
        self.pauseEvent.set()
        log.debug('Tine poller threads paused')

    def resume(self):
        self.pauseEvent.clear()
        log.debug('Tine poller threads resumed running')

    def stop(self):
        self.stopEvent.set()
        log.debug('Tine poller threads stopped')
        for thr in self._threads_dct.values():
            thr.thread.join()

    @property
    def threads_dct(self):
        return self._threads_dct


# debugging

if __name__ == "__main__":
    logFormatter = logging.Formatter(
        "%(asctime)-25.25s %(threadName)-12.12s %(name)-25.24s %(levelname)-10.10s %(message)s")
    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    rootLogger.addHandler(consoleHandler)

    TP = TinePoller()
    add2 = {'tine_dev': 'V2_B', 'tine_property': 'P21.Stellung', 'format': 's'}
    add1 = {'tine_dev': 'PS2_B', 'tine_property': 'P21.Stellung', 'format': 's'}
    TP._add_dev_to_log(add1)
    time.sleep(10)
    TP._add_dev_to_log(add2)
    time.sleep(10)
    TP._add_dev_to_log(add2)
