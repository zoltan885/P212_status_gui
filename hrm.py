#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 20 16:09:14 2024

hrm test file

@author: hegedues
"""

from PyQt5.QtWidgets import (
    QMainWindow,
    QLabel,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QProgressBar,
    QFileDialog,
    QSizePolicy,
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt5 import QtWidgets, uic, QtGui
from pathlib import Path
# import queue
from threading import Thread
from multiprocessing import Event, Process, Pool  # , Queue
from queue import Queue
import multiprocessing
import glob
import sys
import os
import psutil
import time
import datetime
import numpy as np
import atexit
import logging
logFormatter = logging.Formatter(
    "%(asctime)-25.25s %(threadName)-12.12s %(name)-25.24s %(levelname)-10.10s %(message)s")
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.DEBUG)
# logging.getLogger().setLevel(logging.DEBUG)
fileHandler = logging.FileHandler(os.path.join(os.getcwd(), 'log.log'))
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)


try:
    import PyTango as PT
    TANGO = True
except ImportError as e:
    logging.warning(f"{e}")


# resource:
# https://doc.qt.io/qt-5/stylesheet-examples.html
# https://stackoverflow.com/questions/6784084/how-to-pass-arguments-to-functions-by-the-click-of-button-in-pyqt


_coolBlue = '#0d6efd'

_TangoStateColors = {'ON': '#42f545',
                     'OFF': '#f4f7f2',
                     'MOVING': '#427ef5',
                     'STANDBY': '#f5f253',
                     'FAULT': '#cc2b2b',
                     'INIT': '#daa06d',
                     'ALARM': '#eb962f',
                     'DISABLE': '#f037fa',
                     'UNKNOWN': '#808080'}

mots = {'hury': 'hasep212oh:10000/p21/motor/oh_u3.04',
        'hdry': 'hasep212oh:10000/p21/motor/oh_u3.06',
        'hutz': 'hasep212oh:10000/p21/motor/oh_u3.03',
        'hdtz': 'hasep212oh:10000/p21/motor/oh_u3.05',
        'hus ':  'hasep212oh:10000/p21/motor/oh_u3.02',
        'hds ':  'hasep212oh:10000/p21/motor/oh_u3.09',
        'hud ':  'hasep212oh:10000/p21/motor/oh_u4.11',
        }

ctrs = {'upstream': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA'},
        'hud': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent'},
        'downstream': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent'},
        }

props = {'foil': {'property': ('FOILS', 'upstream_counter')},
         }

attrDescriptor = {'position': {'color': '#0d6efd', 'border': '2px solid #0d6efd'},
                  'counter': {'color': '#ff7f50', 'border': '2px solid #ff0000'},
                  'globalProp': {'color': '#10bfde', 'border': '1px #10bfde'},
                  }


FASTTIMER = 0.1
SLOWTIMER = 0.5

PROGRESS = '-|'
GRACE = 0.1


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
        self.startEvent.set()

    def add_attr(self, dev, attr, state=False):
        # connect to the device...
        try:
            attrProxy = PT.AttributeProxy(dev + '/' + attr)
            logging.info(f'Created attribute proxy: {dev}/{attr}')
        except:
            logging.error(f'Could not create attribute proxy: {dev}/{attr}')
            return
        devProxy = None
        if state:
            try:
                devProxy = attrProxy.get_device_proxy()  # PT.DeviceProxy(dev)
                logging.info(f'Created device proxy: {dev}')
            except:
                logging.error(f'Could not create device proxy: {dev}')
                return
        index = len(self.threads) + 1
        thr = Thread(target=self._worker, args=(), kwargs={'index': index,
                                                           'attrProxy': attrProxy,
                                                           'devProxy': devProxy,
                                                           'queue': self.queue})
        thr.start()
        self.threads.append(thr)
        logging.debug(f'Thread (index: {index}) created and started TID: {thr.native_id}')

    def _worker(self, index=None, attrProxy=None, devProxy=None, queue=None):
        logging.debug(f'Worker thread ({index} -> ): started')
        self.startEvent.wait()
        logging.debug(f'Worker thread ({index}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            try:
                # mess['value'] = attrProxy.read()  # this would be nice, but can not be pickled: RuntimeError
                mess['value'] = attrProxy.read().value
                mess['state'] = devProxy.state() if devProxy is not None else PT.DevState.UNKNOWN
                queue.put(mess)
                # logging.debug(f'Message put in queue ({self.queue}): {mess}')
            except:
                pass
            time.sleep(GRACE)
        logging.debug(f'Worker thread ({index}) stopped')

    def add_property(self, prop, host='hasep212oh', port=10000):
        '''
        prop is a tuple with free property and property name: e.g. ('FOILS', 'downstream_counter')
        '''
        try:
            db = PT.Database(host, port)
            logging.info(f'Connected to database: {host}:{port}')
        except:
            logging.error(f'Could not connected to database: {host}:{port}')
            return
        index = len(self.threads) + 1
        thr = Thread(target=self._propertyWorker, args=(), kwargs={'index': index,
                                                                   'db': db,
                                                                   'prop': prop,
                                                                   'queue': self.queue})
        thr.start()
        self.threads.append(thr)
        logging.debug(f'Thread (index: {index}) created and started TID: {thr.native_id}')

    def _propertyWorker(self, index=None, db=None, prop=None, queue=None):
        logging.debug(f'Worker thread ({index} -> {prop}): started')
        self.startEvent.wait()
        logging.debug(f'Worker thread ({index}): running')
        while not self.stopEvent.is_set():
            if self.pauseEvent.is_set():
                time.sleep(0.5)
                continue
            mess = {}
            mess['index'] = index
            try:
                mess['value'] = db.get_property(prop[0], prop[1])[prop[1][0]]
                queue.put(mess)
                # logging.debug(f'Message put in queue ({self.queue}): {mess}')
            except:
                pass
            time.sleep(10*GRACE)
        logging.debug(f'Worker thread ({index}) stopped')

        # this parameter is there for hte horizontal steering
        beamSepOffset = float(db.get_property('LAUE', 'beamSepOffset')['beamSepOffset'][0])

    def start(self):
        self.startEvent.set()
        logging.debug('Poller threads started')

    def pause(self):
        self.pauseEvent.set()
        logging.debug('Poller threads paused')

    def resume(self):
        self.pauseEvent.clear()
        logging.debug('Poller threads resumed running')

    def stop(self):
        self.stopEvent.set()
        logging.debug('Poller threads stopped')
        for thr in self.threads:
            thr.join()


class AttributeRow(QtWidgets.QWidget):
    def __init__(self, label: str, value: float, state: str, attrType='position', formatString='.4f'):
        assert attrType in list(attrDescriptor.keys())
        super(AttributeRow, self).__init__()
        self.formatString = formatString
        self.layout = QHBoxLayout()
        # name label
        self.label = QLabel(label)
        self.label.setMinimumWidth(100)
        self.label.setStyleSheet('''QLabel {
                                            font-size: 30px;
                                            font-weight: 600;
                                            }''')
        # value
        color = attrDescriptor[attrType]['color']
        self.value = QLabel(str(value))
        self.value.setMinimumWidth(150)
        self.value.setStyleSheet('''QLabel {
                                            color: %s;
                                            font-size: 30px;
                                            font-weight: 600;
                                            border-radius: 5px;
                                            border: 2px solid %s;
                                            }''' % (color, color))
        # state
        self.state = QLabel('UNKNOWN')
        self.state.setMinimumWidth(80)
        self.state.setMaximumWidth(90)
        self.state.setStyleSheet('''QLabel {
                                            color: black;
                                            font-size: 30px;
                                            font-weight: 600;
                                            border-radius: 5px;
                                            border: 2px solid black;
                                            }''')

        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.value, 1)
        self.layout.addWidget(self.state, 2)
        self.setLayout(self.layout)

    def update(self, label=None, value=None, state=None, color=None):
        if label is not None:
            self.label.setText(label)
        if value is not None:
            self.value.setText(f'{value:{self.formatString}}')
        if state is not None:
            self.state.setStyleSheet('QLabel {background-color: %s}' % _TangoStateColors[state])
            self.state.setText(state)


class PropertyRow(QtWidgets.QWidget):
    def __init__(self, label: str, value: str):
        super(PropertyRow, self).__init__()

        self.layout = QHBoxLayout()
        # name label
        self.label = QLabel(label)
        self.label.setMinimumWidth(100)
        self.label.setStyleSheet('''QLabel {
                                            font-size: 30px;
                                            font-weight: 600;
                                            }''')
        # value
        color = attrDescriptor['globalProp']['color']
        self.value = QLabel(value)
        self.value.setMinimumWidth(150)
        self.value.setStyleSheet('''QLabel {
                                            color: %s;
                                            font-size: 30px;
                                            font-weight: 600;
                                            border-radius: 5px;
                                            border: 2px solid %s;
                                            }''' % (color, color))
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.value, 1)
        self.setLayout(self.layout)

    def update(self, label=None, value=None):
        pass


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)
        uic.loadUi('hrm.ui', self)
        self.t0 = time.time()
        self.pollers = []
        self.widgets = []
        grid = QVBoxLayout()
        self.poller = Poller()
        self.pollers.append(self.poller)

        for k, v in mots.items():
            w = AttributeRow(k, 0.0000, 'ON', attrType='position')
            self.widgets.append(w)
            grid.addWidget(w)
            self.poller.add_attr(v, 'position', state=True)

        for k, v in ctrs.items():
            w = AttributeRow(k, 0.0000, 'ON', attrType='counter', formatString='.3e')
            self.widgets.append(w)
            grid.addWidget(w)
            self.poller.add_attr(v['dev'], v['attr'], state=False)

        for k, v in props.items():
            w = PropertyRow(k, 'undef')
            self.widgets.append(w)
            grid.addWidget(w)
            self.poller.add_property(v)

        # for i in range(9):
        #     ty = 'counter' if np.random.rand() < 0.4 else 'position'
        #     w = AttributeRow('label', 0.5123, 'ON', attrType=ty)
        #     self.widgets.append(w)
        #     grid.addWidget(w)

        self.frame_2.setLayout(grid)

        self.timerFast = QTimer()
        self.timerFast.start(int(1000*FASTTIMER))
        self.timerFast.timeout.connect(self.updateFromQueue)

        self.timerSlow = QTimer()
        self.timerSlow.start(int(1000*SLOWTIMER))
        self.timerSlow.timeout.connect(self.watchdog)

    # def _upd(self, *args):
    #     key = args[0]
    #     self.widgets[key].value.setText(f'{np.random.rand():.4f}')
    #     state = list(_TangoStateColors)[np.random.randint(1000) % 9]
    #     # self.widgets[key].state.setStyleSheet('QLabel {background-color: %s}' % _TangoStateColors[state])
    #     color = _TangoStateColors[state]
    #     self.widgets[key].state.setStyleSheet('''QLabel {
    #                                             color: %s;
    #                                             font-size: 30px;
    #                                             font-weight: 600;
    #                                             border-radius: 5px;
    #                                             border: 2px solid black;
    #                                             background-color: %s;
    #                                             }''' % (color, color))
    #     self.widgets[key].state.setText(state)

    # def update(self):
    #     for i, w in enumerate(self.widgets):
    #         self._upd(i)

    def _updFromQueue(self, message):
        '''
        this gets a message from the Poller queue
        '''
        if message is None:
            return
        # logging.debug(f'_updQueue: message {message}')
        index = message['index']
        if index == -1:
            return
        # value = message['value']
        # state = str(message['state'])

        # update(label=None, value=None, state=None, color=None):
        self.widgets[index-1].update(value=message['value'], state=str(message['state']))

        # self.widgets[index-1].value.setText(f'{value:.4e}')
        # self.widgets[index-1].state.setStyleSheet('QLabel {background-color: %s}' % _TangoStateColors[state])
        # self.widgets[index-1].state.setText(state)

    def updateFromQueue(self):
        qu = self.poller.queue
        # logging.debug(f'updateFromQueue called {qu}')
        while not qu.empty():
            message = qu.get()
            # logging.debug(f'{message}')
            self._updFromQueue(message)
        time.sleep(0.01)

    def watchdog(self):
        dt = time.time() - self.t0
        if int(2*dt) % 2 == 0:
            self.label_2.setText('-')
        else:
            self.label_2.setText('|')


def exitHandler(pollers):
    for p in pollers:
        p.stop()
    print('BYE')


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWidget()

    pollers = main.pollers
    # for n, m in mots.items():
    #     pollers[0].add_attr(m, 'position')
    # atexit.register(exitHandler, pollers)  # this would be good, but it only handles terminal exits, and not the gui
    app.aboutToQuit.connect(lambda x=pollers: exitHandler(x))
    # app.setStyleSheet(Path('style.qss').read_text())

    main.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
