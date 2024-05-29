#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:06:07 2024

@author: hegedues
"""
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
    QLabel,
    QHBoxLayout,
)
from _settings import attrDescriptor, _TangoStateColors

import logging
log = logging.getLogger(__name__)


class AttributeRow(QtWidgets.QWidget):
    def __init__(self, label: str, value: float, state: str, attrType='position', formatString='.4f', widgetStyle='number', toolTip=None):
        assert attrType in list(attrDescriptor.keys())
        self.attrType = attrType
        super(AttributeRow, self).__init__()
        self.formatString = formatString
        self.widgetStyle = widgetStyle
        self.layout = QHBoxLayout()
        # name label
        self.label = QLabel(label)
        self.label.setMaximumHeight(40)
        self.label.setMinimumWidth(150)
        self.label.setStyleSheet('''QLabel {
                                            font-size: 26px;
                                            font-weight: 600;
                                            }''')
        # value
        color = attrDescriptor[self.attrType]['color']
        self.value = QLabel(str(value))
        if toolTip is not None:
            self.value.setToolTip(toolTip)
        self.label.setMaximumHeight(40)
        self.value.setMinimumWidth(150)
        self.value.setStyleSheet('''QLabel {
                                            color: %s;
                                            font-size: 30px;
                                            font-weight: 600;
                                            border-radius: 3px;
                                            border: 2px solid black;
                                            }''' % (color))
        # state
        self.state = QLabel('UNKNOWN')
        self.label.setMaximumHeight(40)
        self.state.setMinimumWidth(80)
        self.state.setMaximumWidth(90)
        self.state.setStyleSheet('''QLabel {
                                            color: black;
                                            font-size: 30px;
                                            font-weight: 600;
                                            border-radius: 3px;
                                            border: 2px solid black;
                                            }''')

        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.value, 1)
        if self.widgetStyle == 'full':
            self.layout.addWidget(self.state, 2)
        self.setLayout(self.layout)

    def update(self, message:dict):
        # logging.debug(f'WIDGET UPDATE: {value}, {state}')
        message.setdefault('label', None)
        label = message['label']
        message.setdefault('value', None)
        value = message['value']
        message.setdefault('state', None)
        state = str(message['state'])
        message.setdefault('color', None)
        color = message['color']

        if self.widgetStyle == 'nostate':
            state = None
        if label is not None:
            self.label.setText(label)
        if value is not None:
            self.value.setText(f'{value:{self.formatString}}')
        elif value is None:
            self.value.setText('None')
        if self.widgetStyle == 'frame' and state is not None:
            color = attrDescriptor[self.attrType]['color']
            self.value.setStyleSheet('''QLabel {
                                                color: %s;
                                                font-size: 30px;
                                                font-weight: 600;
                                                border-radius: 3px;
                                                border: 2px solid %s;
                                                }''' % (color, _TangoStateColors[state]))
        elif self.widgetStyle == 'number' and state is not None:
            self.value.setStyleSheet('''QLabel {
                                                color: %s;
                                                font-size: 30px;
                                                font-weight: 600;
                                                }''' % (_TangoStateColors[state]))
        elif self.widgetStyle == 'background' and state is not None:
            self.value.setStyleSheet('''QLabel {
                                                background-color: %s;
                                                color: black;
                                                font-size: 30px;
                                                font-weight: 600;
                                                border-radius: 3px;
                                                }''' % (_TangoStateColors[state]))
        if state is not None:
            self.state.setStyleSheet('QLabel {background-color: %s; border-radius: 3px;}' % _TangoStateColors[state])
            self.state.setText(state)


class PropertyRow(QtWidgets.QWidget):
    def __init__(self, label: str, value: str, formatString=None, toolTip=None):
        super(PropertyRow, self).__init__()
        self.formatString = formatString
        self.layout = QHBoxLayout()
        # name label
        self.label = QLabel(label)
        self.label.setMinimumWidth(150)
        self.label.setStyleSheet('''QLabel {
                                            font-size: 26px;
                                            font-weight: 600;
                                            }''')
        # value
        color = attrDescriptor['globalProp']['color']
        self.value = QLabel(value)
        if toolTip is not None:
            self.value.setToolTip(toolTip)
        self.value.setMinimumWidth(150)
        self.value.setStyleSheet('''QLabel {
                                            color: %s;
                                            font-size: 30px;
                                            font-weight: 600;
                                            }''' % (color))
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.value, 1)
        self.setLayout(self.layout)

    def update(self, message:dict):
        message.setdefault('label', None)
        label = message['label']
        message.setdefault('value', None)
        value = message['value']
        message.setdefault('state', None)
        state = str(message['state'])
        message.setdefault('color', None)
        color = message['color']
        if label is not None:
            self.label.setText(label)
        if value is not None:
            if self.formatString is not None:
                self.value.setText(f'{value:{self.formatString}}')
            else:
                self.value.setText(f'{value}')
