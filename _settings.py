#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:10:15 2024

@author: hegedues
"""


blue = '#0d6efd'

attrDescriptor = {'position': {'color': '#000000', 'border': '2px solid #0d6efd'},
                  'counter': {'color': '#ff7f50', 'border': '2px solid #ff0000'},
                  'globalProp': {'color': '#10bfde', 'border': '1px #10bfde'},
                  'tine': {'color': '#ff7f50', 'border': '2px solid #ff0000'},
                  }

_TangoStateColors = {'ON': '#6beda5',  # '#42f545',
                     'OFF': '#f4f7f2',
                     'MOVING': '#427ef5',
                     'STANDBY': '#f5f253',
                     'FAULT': '#cc2b2b',
                     'INIT': '#daa06d',
                     'ALARM': '#eb962f',
                     'DISABLE': '#f037fa',
                     'UNKNOWN': '#808080',
                     None: '#808080'}

_defaults = {'attr': {'format': '.4f',
                      'widgetStyle': 'background',
                      },
             'prop': {'host': 'hasep212oh',
                      },
             'fontsize': 28,
             }

_tine_state_like_property = {0: {'color': '#808080', 'text': 'UNKNOWN'},
                             1: {'color': '#fc4e03', 'text': 'CLOSED'},
                             2: {'color': '#016603', 'text': 'OPEN'},
                             }
