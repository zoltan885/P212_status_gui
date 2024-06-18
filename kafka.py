#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 17 16:33:25 2024

@author: hegedues
"""

# https://docs.confluent.io/kafka-clients/python/current/overview.html
# https://console.upstash.com/kafka/2a11cf44-ea72-481c-8be2-7c1178e8d8de?tab=details


from confluent_kafka import Producer
import socket
import json
import time

from threading import Thread
from multiprocessing import Event, Process, Pool  # , Queue
from queue import Queue
import logging
log = logging.getLogger(__name__)

conf = {'bootstrap.servers': 'vital-shepherd-6492-eu2-kafka.upstash.io:9092',
        'sasl.mechanism': 'SCRAM-SHA-256',
        'security.protocol': 'SASL_SSL',
        'sasl.username': 'dml0YWwtc2hlcGhlcmQtNjQ5MiQwo9Jx5TZtgbgkR0M0_gNwluio90evPapj0_Q',
        'sasl.password': 'MTU5OGFkMDgtMjhiMC00M2Q4LTljM2MtMzBkYjczYTY5YWRj',
        'client.id': socket.gethostname()
        }

SERVER = 'vital-shepherd-6492-eu2-kafka.upstash.io:9092'
USER = 'dml0YWwtc2hlcGhlcmQtNjQ5MiQwo9Jx5TZtgbgkR0M0_gNwluio90evPapj0_Q'
PASSWORD = 'MTU5OGFkMDgtMjhiMC00M2Q4LTljM2MtMzBkYjczYTY5YWRj'


GRACE = 5


class kafkaProducer():
    '''
    the Queue should be a 1 long queue
    '''

    def __init__(self,
                 queue: Queue,
                 server: str = SERVER,
                 user: str = USER,
                 pw: str = PASSWORD,
                 ):
        self.queue = queue
        self.config = {'bootstrap.servers': server,
                       'sasl.mechanism': 'SCRAM-SHA-256',
                       'security.protocol': 'SASL_SSL',
                       'sasl.username': user,
                       'sasl.password': pw,
                       'client.id': socket.gethostname()
                       }
        self.producer = Producer(self.config)

        self.pauseEvent = Event()
        self.pauseEvent.set()
        self.stopEvent = Event()

        self.thr = Thread(target=self._produce_worker, args=(), kwargs={'queue': self.queue, })
        self.thr.start()

    def _produce_worker(self, queue, channel: str = 'P212_status', key: str = 'app_message'):
        log.info('Kafka producer instantiated')
        while not self.stopEvent.is_set():
            # log.debug('In the loop')
            if not self.pauseEvent.is_set():
                # log.debug('Not paused')
                if not queue.empty():
                    # log.debug('Queue not empty')
                    try:
                        serial_payload = json.dumps(queue.get())
                        self.producer.produce(channel, key=key, value=serial_payload)
                    except:
                        pass
                self.producer.flush()
            t0 = time.time()
            while time.time()-t0 < GRACE:
                time.sleep(0.1)
                if self.stopEvent.is_set():
                    break
        log.debug('Kafka producer thread stopped')

    def pause(self):
        self.pauseEvent.set()
        log.debug('Kafka thread paused')

    def resume(self):
        self.pauseEvent.clear()
        log.debug('Kafka thread resumed running')

    def stop(self):
        self.stopEvent.set()
        log.debug('Kafka thread stopped')
        self.thr.join()
