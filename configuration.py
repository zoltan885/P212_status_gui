#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

grouping = {
    'tabs': {
        'frontend': {
            'scroll1': ['PETRA', 'misc'],
            'scroll2': ['Frontend_slits',
                        'Undulator'
                        ],
        },
        'Optical Hutch': {
            'scroll1': ['HRM',
                        'ctrs',
                        'props']
        },
        'Experimental Hutch': {
            'scroll1': ['diffractometer',
                        # 'Server',
                        ]
        },
    },
}

misc = {'RC': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'BeamCurrent', 'format': '.1f'},
        }

PETRA = {'ring current': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'BeamCurrent', 'format': '.1f', 'condition': 'ring_condition'},
         'N_bunches': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'NumberOfBunches', 'format': 'd'},
         'Lifetime': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'BeamLifetime', 'format': '.1f'},
         'Ring energy': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'Energy', 'format': '.2f'},
         'Topup': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'TopUpStatus', 'format': 'd'},
         'OrbitRMSX': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'orbitRMSX', 'format': '.1f'},
         'OrbitRMSY': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'orbitRMSY', 'format': '.1f'},
         'FastOrbit': {'dev': 'hasep212oh:10000/PETRA/GLOBALS/keyword', 'attr': 'FastOrbitFBStatusText', 'format': 's'},
         }
Undulator = {'gap': {'dev': 'hasep212oh:10000/p21/plcundulator/oh.01', 'attr': 'CurrentGap', 'format': '.0f'},
             }
vacuum_valves = {}

lm_cams = {}

Laue_mono = {}

Frontend_slits = {'ps1off': {'dev': 'hasepfe:10000/p21/motor/fe.34', 'attr': 'position', 'widgetStyle': 'full'},
                  'ps1gap': {'dev': 'hasepfe:10000/p21/motor/fe.33', 'attr': 'position', 'widgetStyle': 'frame'},
                  'ps2off': {'dev': 'hasepfe:10000/p21/motor/fe.36', 'attr': 'position', 'widgetStyle': 'number'},
                  'ps2gap': {'dev': 'hasepfe:10000/p21/motor/fe.35', 'attr': 'position', 'widgetStyle': 'background'},
                  'ps2in': {'dev': 'hasepfe:10000/p21/motor/fe.37', 'attr': 'position', 'widgetStyle': 'nostate'},
                  'ps2out': {'dev': 'hasepfe:10000/p21/motor/fe.38', 'attr': 'position'},
                  }


HRM = {'hury': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.04', 'attr': 'position', 'format': '.0f'},
       'hdry': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.06', 'attr': 'position', 'format': '.0f'},
       'hutz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.03', 'attr': 'position'},
       'hdtz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.05', 'attr': 'position'},
       'hus ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.02', 'attr': 'position'},
       'hds ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.09', 'attr': 'position'},
       'hud ': {'dev': 'hasep212oh:10000/p21/motor/oh_u4.11', 'attr': 'position'},
       }

ctrs = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.2e', 'widgetStyle': 'background'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.2e', 'widgetStyle': 'background'},
        }

props = {'foil': {'property': ('FOILS', 'current_foil'), 'host': 'hasep212oh'},
         'energy': {'property': ('GLOBAL', 'ENERGY'), 'host': 'hasep212oh'},
         'absorber': {'property': ('GLOBAL', 'ABSORBER'), 'host': 'hasep212oh'},
         }

diffractometer = {'idtz2': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.06', 'attr': 'position'},
                  'idty2': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.05', 'attr': 'position'},
                  'idtx2': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.10', 'attr': 'position'},
                  'idry2': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.04', 'attr': 'position'},
                  'idrx2': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.09', 'attr': 'position'},
                  'idrz1': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u2.05', 'attr': 'position'},
                  'idty1': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.14', 'attr': 'position'},
                  'idry1': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u1.13', 'attr': 'position'},
                  }
symmetrie = {}

Server = {'Keithley': {'server': 'Keithley2602b/eh3_1'},
          }
