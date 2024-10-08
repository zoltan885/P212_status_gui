#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 20 16:09:14 2024

hrm test file

@author: hegedues
"""

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
from gui_parts import AttributeRow, PropertyRow
from poller import Poller
from tine_poller import TinePoller
from queue import Queue
from kafka import kafkaProducer
from status_bar import Ui_status_widget  # this should be changed

import importlib
if len(sys.argv) > 1:
    conf_name = sys.argv[1]
    conf = importlib.import_module(conf_name)
    logging.info(f'{sys.argv[1]} imported')
else:
    import configuration as conf

VERSION = {'major': 1, 'minor': 2, 'patch': 1}

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
KAFKATIMER = 1

PROGRESS = '-|'
DEFAULT_FLOAT = None


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.setMinimumSize(500, 500)
        # super.__init__(*args, **kwargs)
        self.comm_queue = Queue(20000)
        self.kafka_queue = Queue(1)

        self.pollers = []  # this is to keep track of the current state by merging the current_state attr of all pollers
        self.threads_to_stop = []

        self.poller = Poller(queue=self.comm_queue)
        self.pollers.append(self.poller)
        self.threads_to_stop.append(self.poller)

        self.tine_poller = TinePoller(queue=self.comm_queue)
        self.pollers.append(self.tine_poller)
        self.threads_to_stop.append(self.tine_poller)

        #self.kafka = kafkaProducer(self.kafka_queue)
        #self.threads_to_stop.append(self.kafka)

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
        deb_menu = menubar.addMenu('Debug')

        start_kafka_action = QAction("Start KAFKA", self)
        #start_kafka_action.triggered.connect(self._start_kafka)
        deb_menu.addAction(start_kafka_action)

        stop_kafka_action = QAction("Pause KAFKA", self)
        #stop_kafka_action.triggered.connect(self._stop_kafka)
        deb_menu.addAction(stop_kafka_action)

        self.mainLayout = QHBoxLayout()

        self.t0 = time.time()

        self.widgets = []
        self.scrolls = []
        self.all_update_widgets = defaultdict(list)

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
                                                        font-size: %dpx;
                                                        font-weight: 600;
                                                        border: 2px solid gray;
                                                        border-radius: 5px;
                                                        margin-top: 2.5ex;
                                                        }''' % (int(_defaults['fontsize'])))
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
                            self.poller.add_attr(v, state=True)
                        elif 'property' in v.keys():
                            ID = utilities.create_ID(v)
                            widget = PropertyRow(k, 'undef', toolTip=ID)
                            group_layout.addWidget(widget)
                            v.setdefault('host', _defaults['prop']['host'])
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            v.setdefault('host', _defaults['prop']['host'])
                            self.poller.add_property(v, host=v['host'], port=10000)
                        elif 'server' in v.keys():
                            ID = utilities.create_ID(v)
                            widget = PropertyRow(k, 'undef', toolTip=ID)
                            group_layout.addWidget(widget)
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            self.poller.add_server(v)
                        elif 'tine_property' in v.keys():
                            ID = utilities.create_ID(v)
                            # widget = PropertyRow(k, 'undef', toolTip=ID)

                            attr_type = 'tine'
                            v.setdefault('format', 's')
                            v.setdefault('widgetStyle', _defaults['attr']['widgetStyle'])
                            v.setdefault('logged', False)
                            widget = AttributeRow(k, DEFAULT_FLOAT, 'ON', attrType=attr_type,
                                                  formatString=v['format'], widgetStyle=v['widgetStyle'], toolTip=ID)
                            group_layout.addWidget(widget)
                            self.widgets.append(widget)
                            self.all_update_widgets[ID].append(widget)
                            self.tine_poller.add_dev_to_log(v)

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
        # self.statusBar().showMessage("this is status bar")
        _status_bar_widget = QWidget()
        self.statusBarWidget = Ui_status_widget()
        self.statusBarWidget.setupUi(_status_bar_widget)
        self.statusBar().addWidget(_status_bar_widget)

        self.show()

        self.timerFast = QTimer()
        self.timerFast.start(int(1000*FASTTIMER))
        # self.timerFast.timeout.connect(self.updateFromQueue)
        self.timerFast.timeout.connect(self.new_update_from_queue)
        self.timerSlow = QTimer()
        self.timerSlow.start(int(1000*SLOWTIMER))
        self.timerSlow.timeout.connect(self.heartbeat)
        #self.kafkaTimer = QTimer()
        #self.kafkaTimer.start(int(1000*KAFKATIMER))
        #self.kafkaTimer.timeout.connect(self._update_kafka_queue)

#        logging.debug(self.all_update_widgets)

    # the next two functions should be in the kafka module

    def _combine_states(self, state_dcts: list):
        assert isinstance(state_dcts, list), 'state_dcts should be a list'
        if len(state_dcts) == 1:
            return state_dcts[0]
        dct = state_dcts[0].copy()
        for d in state_dcts[1:]:
            dct.update(d)
        return dct

    def _update_kafka_queue(self):
        # logging.debug('Putting stuff into the Kafka queue')
        if not self.kafka.queue.empty():
            # empty the queue if not yet emptied by the kafkaProducer
            try:
                _ = self.kafka.queue.get_nowait()
            except:
                pass
        current_states = [p.current_state for p in self.pollers]
        current_state = self._combine_states(current_states)
        try:
            self.kafka.queue.put_nowait(current_state)
            # logging.debug(f'Merged current state put int the kafka queue: {current_state}')
        except:
            pass

    def _start_kafka(self):
        logging.debug('Action: resume kafka operation')
        self.kafka.resume()

    def _stop_kafka(self):
        logging.debug('Action: pause kafka operation')
        self.kafka.pause()

    def new_update_from_queue(self):
        # qu = self.poller.queue
        qu = self.comm_queue
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

    def heartbeat(self):
        '''
        simple text updater to show that the application is still responsive
        '''
        dt = time.time() - self.t0
        if int(dt) % 2 == 0:
            self.statusBarWidget.label_0.setText("-")
        else:
            self.statusBarWidget.label_0.setText("|")

        if int(dt) % 2 == 0:
            _color1, _color2 = '#fc4e03', '#016603'
        else:
            _color1, _color2 = '#016603', '#fc4e03'
        self.statusBarWidget.label_1.setStyleSheet('''QLabel {background-color: %s;}''' % (_color1))
        self.statusBarWidget.label_2.setStyleSheet('''QLabel {background-color: %s;}''' % (_color2))
        self.statusBarWidget.label_3.setStyleSheet('''QLabel {background-color: %s;}''' % (_color1))
        self.statusBarWidget.label_4.setStyleSheet('''QLabel {background-color: %s;}''' % (_color2))
        self.statusBarWidget.label_5.setStyleSheet('''QLabel {background-color: %s;}''' % (_color1))
        self.statusBarWidget.label_6.setStyleSheet('''QLabel {background-color: %s;}''' % (_color2))

    def tabChanged(self):
        logging.info(self.centralWidget.currentIndex())


def exitHandler(pollers):
    for p in pollers:
        p.stop()
    print('BYE')


def main():
    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow()

    threads_to_stop = main.threads_to_stop
    # atexit.register(exitHandler, pollers)  # this would be good, but it only handles terminal exits, and not the gui
    app.aboutToQuit.connect(lambda x=threads_to_stop: exitHandler(x))
    # app.setStyleSheet(Path('style.qss').read_text())

    main.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
