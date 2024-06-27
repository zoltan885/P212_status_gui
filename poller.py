#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 09:56:34 2024

@author: hegedues
"""
import utilities
import conditions
import numpy as np
import time
import os
from collections import namedtuple, deque
import requests

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

GRACE = 0.1
LOGTIME = 1
DEQUEUE_MAX_SIZE = 2000
logtuple = namedtuple('log', ['time', 'value'])
threadtuple = namedtuple('thread', ['index', 'thread'])
statetuple = namedtuple('state', ['value', 'state'])

TINE_COLORS = {'0': 'UNKNOWN', '1': 'ALARM', '2': 'ON'}

# run an external process and catch the output
# https://stackoverflow.com/questions/4760215/running-shell-command-and-capturing-the-output
# via ssh
# https://stackoverflow.com/questions/3586106/perform-commands-over-ssh-with-python
# inter-process communication
# https://discuss.python.org/t/version-of-multiprocessing-queue-that-works-with-unrelated-processes/27699/2


class Poller():
    '''
    class to poll attributes
    to add attributes call the add_attr method
    the read values end up in the queue of the class as a dict
    '''

    def __init__(self, queue: Queue = None):
        self.startEvent = Event()
        self.pauseEvent = Event()
        self.stopEvent = Event()
        if not queue:
            self.queue = Queue(20000)
        else:
            self.queue = queue
        self.kafka_queue = Queue(1)
        self._threads_dct = {}
        self.log = {}  # this is in preparation to some sort of logging even if only for moving average for smooth values
        self.current_state = {}  # this is an updating dict to hold the current state (meant for external appl)
        self.last_state = []  # this is to record the last state
        self._grace = GRACE  # this could then be set externally

        self.start()

    def add_attr(self, attrdct: dict, state: bool = False):
        dev = attrdct['dev']
        attr = attrdct['attr']
        logged = attrdct['logged']
        ID = utilities.create_ID(attrdct)
        if ID in self._threads_dct.keys():
            logging.info(f'Thread with ID {ID} already exists')
            return
        try:
            attrProxy = PT.AttributeProxy(dev + '/' + attr)
            log.info(f'Created attribute proxy: {dev}/{attr}')
        except:
            log.error(f'Could not create attribute proxy: {dev}/{attr}')
            return
        devProxy = None
        if state:
            try:
                devProxy = attrProxy.get_device_proxy()  # PT.DeviceProxy(dev)
                log.info(f'Created device proxy: {dev}')
            except:
                log.error(f'Could not create device proxy: {dev}')
                return
        index = len(list(self._threads_dct.keys())) + 1
        thr = Thread(target=self._attribute_worker, args=(), kwargs={'index': index,
                                                                     'attrProxy': attrProxy,
                                                                     'devProxy': devProxy,
                                                                     'queue': self.queue,
                                                                     'ID': ID,
                                                                     'logged': logged})
        thr.start()
        if logged:
            logging.debug('Added logged attribute {attr}')
            self.log[ID] = deque(maxlen=DEQUEUE_MAX_SIZE)
        self.current_state[ID] = None
        self._threads_dct[ID] = threadtuple(index, thr)
        log.debug(f'Thread (index: {index}, ID: {ID}) created and started TID: {thr.native_id}')

    def _attribute_worker(self, index: int = None, ID: str = None, attrProxy=None, devProxy=None, queue=None, logged=False):
        log.debug(f'Worker thread ({index} -> {ID}): started')
        self.startEvent.wait()
        log.debug(f'Worker thread ({index}): running')
        last_log = time.time()
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            mess['ID'] = ID
            try:
                # mess['value'] = attrProxy.read()  # this would be nice, but can not be pickled: RuntimeError
                mess['value'] = attrProxy.read().value
                mess['state'] = devProxy.state() if devProxy is not None else PT.DevState.UNKNOWN
                # log.debug(f'Message put in queue ({self.queue}): {mess}')
                if logged and time.time()-last_log > LOGTIME:
                    self.log[ID].append(logtuple(time.time(), mess['value']))
#                    log.debug(f"{mess['value']} added to log: current log size: {len(self.log[ID])}")
                    last_log = time.time()
                self.current_state[ID] = statetuple(mess['value'], str(mess['state']))
            except:
                mess['value'] = None
                mess['state'] = PT.DevState.UNKNOWN
            queue.put(mess)
            time.sleep(self._grace)
        log.debug(f'Worker thread ({index} {ID}) stopped')

    def add_property(self, prop: tuple, host: str = 'hasep212oh', port: int = 10000):
        '''
        prop is a tuple with free property and property name: e.g. ('FOILS', 'downstream_counter')
        '''
        ID = utilities.create_ID(prop)
        if ID in self._threads_dct.keys():
            logging.info(f'Thread with ID {ID} already exists')
            return
        try:
            db = PT.Database(host, port)
            log.info(f'Connected to database: {host}:{port}')
        except:
            log.error(f'Could not connected to database: {host}:{port}')
            return
        index = len(list(self._threads_dct.keys())) + 1
        thr = Thread(target=self._property_worker, args=(), kwargs={'index': index,
                                                                    'db': db,
                                                                    'prop': prop,
                                                                    'queue': self.queue,
                                                                    'ID': ID})
        thr.start()
        self.current_state[ID] = None
        self._threads_dct[ID] = threadtuple(index, thr)
        log.debug(f'Thread (index: {index} ID: {ID}) created and started TID: {thr.native_id}')

    def _property_worker(self, index: int = None, ID: str = None, db=None, prop=None, queue=None):
        log.debug(f'Worker thread ({index} -> {ID}): started')
        prop = prop['property']
        self.startEvent.wait()
        log.debug(f'Worker thread ({index}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            mess['ID'] = ID
            mess['state'] = 'UNDEFINED'
            try:
                mess['value'] = db.get_property(prop[0], prop[1])[prop[1]][0]
                # log.debug(f'Message put in queue ({self.queue}): {mess}')
                self.current_state[ID] = statetuple(mess['value'], mess['state'])
            except Exception as e:
                log.error(e)
            queue.put(mess)
            time.sleep(10*self._grace)
        log.debug(f'Worker thread ({index} {ID}) stopped')

    def add_server(self, server: str):
        ID = utilities.create_ID(server)
        if ID in self._threads_dct.keys():
            logging.info(f'Thread with ID {ID} already exists')
            return
        index = len(list(self._threads_dct.keys())) + 1
        thr = Thread(target=self._server_worker, args=(), kwargs={'server': server,
                                                                  'index': index,
                                                                  'ID': ID,
                                                                  'queue': self.queue,
                                                                  })
        thr.start()

        self._threads_dct[ID] = threadtuple(index, thr)
        log.debug(f'Thread (index: {index} ID: {ID}) created and started TID: {thr.native_id}')

    def _server_worker(self, server: str, index: int, ID: str, queue: Queue):
        log.debug(f'Worker thread ({index} -> {ID}): started')
        self.startEvent.wait()
        log.debug(f'Worker thread ({index}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            mess['ID'] = ID
            mess['state'] = 'UNDEFINED'
            try:
                ans = subprocess.run(['TngUtility3.py', '--list', server], capture_output=True, text=True).stdout
                logging.debug(f'FROM TNGUTILITY: {ans}')
                status = ans.strip().rpartition('\n')[2].strip().split()[1]
                mess['value'] = status
            except:
                mess['value'] = 'unknown'
            queue.put(mess)
            log.debug(f'Message put in queue ({self.queue}): {mess}')
            # this is for the thread to quickly terminate
            t = time.time()
            while not self.stopEvent.is_set() and time.time()-t < 100*self._grace:
                time.sleep(0.01)
        log.debug(f'Worker thread ({index} {ID}) stopped')

    def add_tine(self, tineaddr: str):
        ID = utilities.create_ID(tineaddr)
        if ID in self._threads_dct.keys():
            logging.info(f'Thread with ID {ID} already exists')
            return
        index = len(list(self._threads_dct.keys())) + 1
        thr = Thread(target=self._tine_worker, args=(), kwargs={'tineaddr': tineaddr,
                                                                'index': index,
                                                                'ID': ID,
                                                                'queue': self.queue,
                                                                })
        thr.start()
        self._threads_dct[ID] = threadtuple(index, thr)
        log.debug(f'Thread (index: {index} ID: {ID}) created and started TID: {thr.native_id}')

    def _tine_worker(self, tineaddr: str, index: int, ID: str, queue: Queue):
        tine_dev = tineaddr['tine_dev']
        tine_prop = tineaddr['tine_property']
        log.debug(f'Worker thread ({index} -> {ID}): started')
        self.startEvent.wait()
        log.debug(f'Worker thread ({index}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            mess['ID'] = ID
            mess['state'] = 'UNKNOWN'
            try:
                url = TINEBASEADDRESS + tine_dev + '/' + tine_prop + '/?content=JSON'
                # log.debug(f'URL: {url}')
                resp = requests.get(url, timeout=(0.2, 0.2))
                # log.debug(f'RESPONSE: {resp.json()}')
                last_state = resp.json()['data'][0]
                mess['value'] = last_state
                self.current_state[ID] = statetuple(mess['value'], str(mess['state']))
                mess['state'] = TINE_COLORS[str(last_state)]
            except:
                mess['value'] = 'unknown'
            queue.put(mess)
            # log.debug(f'Message put in queue ({self.queue}): {mess}')
            # this is for the thread to quickly terminate
            t = time.time()
            while not self.stopEvent.is_set() and time.time()-t < 10*self._grace:
                time.sleep(0.01)
        log.debug(f'Worker thread ({index} {ID}) stopped')

    def add_to_logging(self):
        pass

    def start(self):
        self.startEvent.set()
        log.debug('Poller threads started')

    def pause(self):
        self.pauseEvent.set()
        log.debug('Poller threads paused')

    def resume(self):
        self.pauseEvent.clear()
        log.debug('Poller threads resumed running')

    def stop(self):
        self.stopEvent.set()
        log.debug('Poller threads stopped')
        for thr in self._threads_dct.values():
            thr.thread.join()

    @property
    def threads_dct(self):
        return self._threads_dct
