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

server = 'vital-shepherd-6492-eu2-kafka.upstash.io:9092'
user = 'dml0YWwtc2hlcGhlcmQtNjQ5MiQwo9Jx5TZtgbgkR0M0_gNwluio90evPapj0_Q'
pw = 'MTU5OGFkMDgtMjhiMC00M2Q4LTljM2MtMzBkYjczYTY5YWRj'


GRACE = 5


class kafkaProducer():
    def __init__(self,
                 server: str = 'vital-shepherd-6492-eu2-kafka.upstash.io:9092',
                 user: str = 'dml0YWwtc2hlcGhlcmQtNjQ5MiQwo9Jx5TZtgbgkR0M0_gNwluio90evPapj0_Q',
                 pw: str = 'MTU5OGFkMDgtMjhiMC00M2Q4LTljM2MtMzBkYjczYTY5YWRj'):
        self.config = {'bootstrap.servers': server,
                       'sasl.mechanism': 'SCRAM-SHA-256',
                       'security.protocol': 'SASL_SSL',
                       'sasl.username': user,
                       'sasl.password': pw,
                       'client.id': socket.gethostname()
                       }
        self.producer = Producer(self.config)

        self._run = False

    @property
    def run(self):
        return self._run

    @run.setter
    def run(self, val: bool):
        self._run = val

    def produce(self, payload, channel: str = 'P212_status', key: str = 'app_message'):
        if self._run:
            try:
                serial_payload = json.dumps(payload)
                self.producer.produce(channel, key=key, value=serial_payload)
            except:
                pass
            self.producer.flush()
        time.sleep(GRACE)
