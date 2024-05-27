#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

grouping = {
    'tabs': {
        'frontend': {
            'box1': ['petra'],
            'box2': ['frontend_slits',
                     'undulator'
                     ],
        },
        'Optical Hutch': {
            'box1': ['mots',
                     'ctrs',
                     'props']
        }
    },
}

petra = {'ring current': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'BeamCurrent', 'format': '.1f'},
         'topup': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'TopUpStatus', 'format': 'd'},
         'orbitRMSX': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'orbitRMSX', 'format': '.1f'},
         'orbitRMSY': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'orbitRMSY', 'format': '.1f'},
         'fastOrbit': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'FastOrbitFBStatusText', 'format': 's'},
         }
undulator = {'gap': {'dev': 'hasep212oh:10000/p21/plcundulator/oh.01', 'attr': 'CurrentGap', 'format': '.0f'},
             }
vacuum_valves = {}

lm_cams = {}

frontend_slits = {'ps1off': {'dev': 'hasepfe:10000/p21/motor/fe.34', 'attr': 'position', 'widgetStyle': 'full'},
                  'ps1gap': {'dev': 'hasepfe:10000/p21/motor/fe.33', 'attr': 'position', 'widgetStyle': 'frame'},
                  'ps2off': {'dev': 'hasepfe:10000/p21/motor/fe.36', 'attr': 'position', 'widgetStyle': 'number'},
                  'ps2gap': {'dev': 'hasepfe:10000/p21/motor/fe.35', 'attr': 'position', 'widgetStyle': 'background'},
                  'ps2in': {'dev': 'hasepfe:10000/p21/motor/fe.37', 'attr': 'position', 'widgetStyle': 'nostate'},
                  'ps2out': {'dev': 'hasepfe:10000/p21/motor/fe.38', 'attr': 'position'},
                  }


mots = {'hury': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.04', 'attr': 'position', 'format': '.0f'},
        'hdry': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.06', 'attr': 'position', 'format': '.0f'},
        'hutz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.03', 'attr': 'position'},
        'hdtz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.05', 'attr': 'position'},
        'hus ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.02', 'attr': 'position'},
        'hds ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.09', 'attr': 'position'},
        'hud ': {'dev': 'hasep212oh:10000/p21/motor/oh_u4.11', 'attr': 'position'},
        }

ctrs = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.2e', 'widgetStyle': 'frame'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'frame'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.2e', 'widgetStyle': 'frame'},
        }

props = {'foil': {'property': ('FOILS', 'current_foil'), 'host': 'hasep212oh'},
         'energy': {'property': ('GLOBAL', 'ENERGY'), 'host': 'hasep212oh'},
         'absorber': {'property': ('GLOBAL', 'ABSORBER'), 'host': 'hasep212oh'},
         }
