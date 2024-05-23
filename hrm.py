#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 20 16:09:14 2024

hrm test file

@author: hegedues
"""

from poller import Poller
from gui_parts import AttributeRow, PropertyRow
import configuration as conf
# from configuration import mots, props, ctrs, frontend, undulator

from PyQt5.QtWidgets import (
    QMainWindow,
    QLabel,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from PyQt5.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt5 import QtWidgets, uic

import sys
import os
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


# resources:
# https://doc.qt.io/qt-5/stylesheet-examples.html
# https://stackoverflow.com/questions/6784084/how-to-pass-arguments-to-functions-by-the-click-of-button-in-pyqt
# https://stackoverflow.com/questions/15727420/using-logging-in-multiple-modules
# Detachable tabs...
# https://stackoverflow.com/questions/47267195/in-pyqt-is-it-possible-to-detach-tabs-from-a-qtabwidget
# Quest DB
# https://py-questdb-client.readthedocs.io/en/latest/

_coolBlue = '#0d6efd'


FASTTIMER = 0.1
SLOWTIMER = 0.5

PROGRESS = '-|'


class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(MainWidget, self).__init__(*args, **kwargs)
        uic.loadUi('hrm.ui', self)
        self.t0 = time.time()
        self.pollers = []
        self.widgets = []
        grid = QVBoxLayout()
        grid2 = QVBoxLayout()

        self.poller = Poller()
        self.pollers.append(self.poller)

        for p in conf.visible:
            for k, v in getattr(conf, p).items():
                if 'attr' in v.keys():
                    attr_type = 'position' if v['attr'] == 'position' else 'counter'
                    v.setdefault('format', '.4f')  # should be somewhere in settings
                    v.setdefault('widgetStyle', 'number')
                    w = AttributeRow(k, 0.0000, 'ON', attrType=attr_type,
                                     formatString=v['format'], widgetStyle=v['widgetStyle'])
                    self.widgets.append(w)
                    grid2.addWidget(w)
                    self.poller.add_attr(v['dev'], v['attr'], state=True)
                elif 'property' in v.keys():
                    w = PropertyRow(k, 'undef')
                    self.widgets.append(w)
                    grid2.addWidget(w)
                    v.setdefault('host', 'hasep212oh')  # should be somewhere in settings
                    self.poller.add_property(v, host=v['host'], port=10000)

        self.frame.setLayout(grid)
        self.frame_2.setLayout(grid2)

        self.timerFast = QTimer()
        self.timerFast.start(int(1000*FASTTIMER))
        self.timerFast.timeout.connect(self.updateFromQueue)
        self.timerSlow = QTimer()
        self.timerSlow.start(int(1000*SLOWTIMER))
        self.timerSlow.timeout.connect(self.watchdog)

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
        self.widgets[index-1].update(value=message['value'], state=str(message['state']))

    def updateFromQueue(self):
        qu = self.poller.queue
        # logging.debug(f'updateFromQueue called {qu}')
        while not qu.empty():
            message = qu.get()
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
    # atexit.register(exitHandler, pollers)  # this would be good, but it only handles terminal exits, and not the gui
    app.aboutToQuit.connect(lambda x=pollers: exitHandler(x))
    # app.setStyleSheet(Path('style.qss').read_text())

    main.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
