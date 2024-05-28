#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 09:56:34 2024

@author: hegedues
"""
import numpy as np
import time
import os
from collections import namedtuple

from threading import Thread
from multiprocessing import Event, Process, Pool  # , Queue
from queue import Queue
import logging
log = logging.getLogger(__name__)


try:
    import PyTango as PT
    TANGO = True
except ImportError as e:
    log.warning(f"{e}")


GRACE = 0.1
threadtuple = namedtuple('thread', ['index', 'thread'])


class Poller():
    '''
    class to poll attributes
    to add attributes call the add_attr method
    the read values end up in the queue of the class as a dict
    '''

    def __init__(self):
        self.startEvent = Event()
        self.pauseEvent = Event()
        self.stopEvent = Event()
        self.queue = Queue(20000)
        self.threads = []
        self._threads_dct = {}
        self.log = {}  # this is in preparation to some sort of logging even if only for moving average for smooth values
        self.last_state = []  # this is to record the last state
        self.startEvent.set()

    def add_attr(self, dev: str, attr: str, ID: str = None, state: bool = False, logged: bool = False):
        # check if attr is already polled an return the already existing thread index
        # if f'{dev}/{attr}' in self.threads_dct.keys():
        #    return self.threads_dct[f'{dev}/{attr}'].index
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
        index = len(self.threads) + 1
        thr = Thread(target=self._attribute_worker, args=(), kwargs={'index': index,
                                                                     'attrProxy': attrProxy,
                                                                     'devProxy': devProxy,
                                                                     'queue': self.queue,
                                                                     'ID': ID})
        thr.start()
        self.threads.append(thr)
        self._threads_dct[ID] = threadtuple(index, thr)
        log.debug(f'Thread (index: {index}, ID: {ID}) created and started TID: {thr.native_id}')

    def _attribute_worker(self, index: int = None, ID: str = None, attrProxy=None, devProxy=None, queue=None):
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
            try:
                # mess['value'] = attrProxy.read()  # this would be nice, but can not be pickled: RuntimeError
                mess['value'] = attrProxy.read().value
                mess['state'] = devProxy.state() if devProxy is not None else PT.DevState.UNKNOWN
                # log.debug(f'Message put in queue ({self.queue}): {mess}')
            except:
                mess['value'] = None
                mess['state'] = PT.DevState.UNKNOWN
            queue.put(mess)
            time.sleep(GRACE)
        log.debug(f'Worker thread ({index}) stopped')

    def add_property(self, prop: tuple, host: str = 'hasep212oh', port: int = 10000, ID: str = None):
        '''
        prop is a tuple with free property and property name: e.g. ('FOILS', 'downstream_counter')
        '''
        if ID in self._threads_dct.keys():
            logging.info(f'Thread with ID {ID} already exists')
            return
        try:
            db = PT.Database(host, port)
            log.info(f'Connected to database: {host}:{port}')
        except:
            log.error(f'Could not connected to database: {host}:{port}')
            return
        index = len(self.threads) + 1
        thr = Thread(target=self._property_worker, args=(), kwargs={'index': index,
                                                                    'db': db,
                                                                    'prop': prop,
                                                                    'queue': self.queue,
                                                                    'ID': ID})
        thr.start()
        self.threads.append(thr)

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
            try:
                mess['value'] = db.get_property(prop[0], prop[1])[prop[1]][0]
                queue.put(mess)
                # log.debug(f'Message put in queue ({self.queue}): {mess}')
            except Exception as e:
                log.error(e)
            mess['state'] = 'UNDEFINED'
            time.sleep(10*GRACE)
        log.debug(f'Worker thread ({index}) stopped')

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
        for thr in self.threads:
            thr.join()

    @property
    def threads_dct(self):
        return self._threads_dct
