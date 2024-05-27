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
from _settings import _defaults
# from configuration import mots, props, ctrs, frontend, undulator

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

from PyQt5.QtCore import QRunnable, Qt, QThreadPool, pyqtSignal, QThread, QObject, pyqtSlot, QTimer
from PyQt5 import QtWidgets, uic

from detachable_tabs import DetachableTabWidget

import sys
import os
import time
import datetime
import numpy as np
import atexit
import logging
import uuid
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
SLOWTIMER = 1

PROGRESS = '-|'


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__()
        # super.__init__(*args, **kwargs)
        self.init_UI()

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
        self.all_update_widgets = {}

        self.poller = Poller()
        self.pollers.append(self.poller)

        for tab in conf.grouping['tabs']:
            tabWidget = QSplitter(Qt.Horizontal)
            tabLayout = QHBoxLayout()

            for gr in conf.grouping['tabs'][tab].keys():
                scr = QScrollArea()
                widg = QWidget()
                scroll_layout = QVBoxLayout()
                # checking is missing here (typos can exists in the config file)
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
                            attr_type = 'position' if v['attr'] == 'position' else 'counter'
                            v.setdefault('format', _defaults['attr']['format'])
                            v.setdefault('widgetStyle', _defaults['attr']['widgetStyle'])
                            widget = AttributeRow(k, 0.0000, 'ON', attrType=attr_type,
                                                  formatString=v['format'], widgetStyle=v['widgetStyle'])
                            group_layout.addWidget(widget)
                            self.widgets.append(widget)
                            self.all_update_widgets[f"attr:{v['dev']}/{v['attr']}"] = widget
                            self.poller.add_attr(v['dev'], v['attr'], state=True)

                        elif 'property' in v.keys():
                            widget = PropertyRow(k, 'undef')
                            group_layout.addWidget(widget)
                            v.setdefault('host', _defaults['prop']['host'])
                            self.widgets.append(widget)
                            self.all_update_widgets[f"prop:{v['host']}/{v['property'][0]}/{v['property'][1]}"] = widget
                            self.poller.add_property(v, host=v['host'], port=10000)
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
        self.timerFast.timeout.connect(self.updateFromQueue)
        self.timerSlow = QTimer()
        self.timerSlow.start(int(1000*SLOWTIMER))
        self.timerSlow.timeout.connect(self.watchdog)

        logging.debug(self.all_update_widgets)

    def _updFromQueue(self, message):
        '''
        this gets a message from the Poller queue
        '''
        if message is None:
            return
        logging.debug(f'_updQueue: message {message}')
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
