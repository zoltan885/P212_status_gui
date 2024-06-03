#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 20 16:09:14 2024

hrm test file

@author: hegedues
"""

import uuid
import logging
import atexit
import numpy as np
import datetime
import time
import os
import sys
from detachable_tabs import DetachableTabWidget
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt5.QtWidgets import (
    QMainWindow,
    QLabel,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QSplitter,
    QScrollArea,
    QGroupBox,
    QToolBar,
    QMenu,
    QAction,
)
from collections import defaultdict
import utilities
from _settings import _defaults
import configuration as conf
from gui_parts import AttributeRow, PropertyRow
from poller import Poller
VERSION = {'major': 1, 'minor': 0, 'patch': 0}

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


_coolBlue = '#0d6efd'


FASTTIMER = 0.1
SLOWTIMER = 1

PROGRESS = '-|'
DEFAULT_FLOAT = None


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__()
        # super.__init__(*args, **kwargs)
        self.init_UI()
        self.setWindowTitle(f'P21.2 status v. {".".join([str(_) for _ in VERSION.values()])}')

    def init_UI(self):
        # uic.loadUi('hrm2.ui', self)
        self.centralWidget = DetachableTabWidget()
        self.centralWidget.currentChanged.connect(self.tabChanged)
        self.centralWidget.setTabBarAutoHide(True)
        self.centralWidget.setMovable(True)
        tabBar = self.centralWidget.tabBar

        menubar = self.menuBar()
        menu = menubar.addMenu('Menu')

        self.mainLayout = QHBoxLayout()

        self.t0 = time.time()
        self.pollers = []
        self.widgets = []
        self.scrolls = []
        self.all_update_widgets = defaultdict(list)

        self.poller = Poller()
        self.pollers.append(self.poller)

        for tab in conf.grouping['tabs']:
            tabWidget = QSplitter(Qt.Horizontal)
            tabLayout = QHBoxLayout()

            for gr in conf.grouping['tabs'][tab].keys():
                scr = QScrollArea()
                widg = QWidget()
                scroll_layout = QVBoxLayout()
                # checking is missing here (typos may happen in the config file)
                for coll in conf.grouping['tabs'][tab][gr]:
                    group = QGroupBox(coll)
                    group_layout = QVBoxLayout()
                    group.setStyleSheet('''QGroupBox {
                                                        font-size: 26px;
                                                        font-weight: 600;
                                                        border: 2px solid gray;
                                                        border-radius: 5px;
                                                        margin-top: 2.5ex;
                                                        }''')
                    for k, v in getattr(conf, coll).items():
                        if 'attr' in v.keys():
                            ID = utilities.create_ID(v)
                            attr_type = 'position' if v['attr'] == 'position' else 'counter'
                            v.setdefault('format', _defaults['attr']['format'])
                            v.setdefault('widgetStyle', _defaults['attr']['widgetStyle'])
                            v.setdefault('logged', False)
                            widget = AttributeRow(k, DEFAULT_FLOAT, 'ON', attrType=attr_type,
                                                  formatString=v['format'], widgetStyle=v['widgetStyle'], toolTip=ID)
                            group_layout.addWidget(widget)
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            self.poller.add_attr(v, state=True, ID=ID)
                        elif 'property' in v.keys():
                            ID = utilities.create_ID(v)
                            widget = PropertyRow(k, 'undef', toolTip=ID)
                            group_layout.addWidget(widget)
                            v.setdefault('host', _defaults['prop']['host'])
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            v.setdefault('host', _defaults['prop']['host'])
                            self.poller.add_property(v, host=v['host'], port=10000, ID=ID)
                        elif 'server' in v.keys():
                            ID = utilities.create_ID(v)
                            widget = PropertyRow(k, 'undef', toolTip=ID)
                            group_layout.addWidget(widget)
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            self.poller.add_server(v, ID=ID)

                    group.setLayout(group_layout)
                    scroll_layout.addWidget(group)
                widg.setLayout(scroll_layout)
                scr.setWidget(widg)
                tabLayout.addWidget(scr)

            tabWidget.setLayout(tabLayout)
            self.centralWidget.addTab(tabWidget, tab)
            # tabBar.setTabTextColor(tab, COLORS[tab])

        self.setCentralWidget(self.centralWidget)
        self.centralWidget.setLayout(self.mainLayout)
        self.statusBar().showMessage("this is status bar")
        self.show()

        self.timerFast = QTimer()
        self.timerFast.start(int(1000*FASTTIMER))
        # self.timerFast.timeout.connect(self.updateFromQueue)
        self.timerFast.timeout.connect(self.new_update_from_queue)
        self.timerSlow = QTimer()
        self.timerSlow.start(int(1000*SLOWTIMER))
        self.timerSlow.timeout.connect(self.watchdog)

        logging.debug(self.all_update_widgets)

    def new_update_from_queue(self):
        qu = self.poller.queue
        while not qu.empty():
            message = qu.get()
            self._upd_from_queue(message)
        time.sleep(0.01)

    def _upd_from_queue(self, message):
        # logging.debug(message)
        if message is None:
            return
        if message['index'] == -1:
            return
        ID = message['ID']
        for widget in self.all_update_widgets[ID]:
            # widget.update(value=message['value'], state=str(message['state']))
            widget.update(message)

    def _updFromQueue(self, message):  # deprecated
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

    def updateFromQueue(self):  # deprecated
        qu = self.poller.queue
        # logging.debug(f'updateFromQueue called {qu}')
        while not qu.empty():
            message = qu.get()
            self._updFromQueue(message)
        time.sleep(0.01)

    def watchdog(self):
        dt = time.time() - self.t0
        if int(dt) % 2 == 0:
            self.statusBar().showMessage("-")
        else:
            self.statusBar().showMessage("|")

    def tabChanged(self):
        logging.info(self.centralWidget.currentIndex())


def exitHandler(pollers):
    for p in pollers:
        p.stop()
    print('BYE')


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()

    pollers = main.pollers
    # atexit.register(exitHandler, pollers)  # this would be good, but it only handles terminal exits, and not the gui
    app.aboutToQuit.connect(lambda x=pollers: exitHandler(x))
    # app.setStyleSheet(Path('style.qss').read_text())

    main.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
