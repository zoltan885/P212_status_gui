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
                        'Undulator',
                        'Styles'
                        ],
        },
        'Optical Hutch': {
            'scroll1': ['HRM',
                        'ctrs',
                        'props']
        },
        'Experimental Hutch': {
            'scroll1': ['EH3slits','diffractometer',],
            'scroll2': [
                        'Experiment',
                        # 'Server',
                        ]
        },
        'Misc.': {
             'scroll1': ['Sweep_stuff','InDaBeam',],
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

Frontend_slits = {'ps1off': {'dev': 'hasepfe:10000/p21/motor/fe.34', 'attr': 'position'},
                  'ps1gap': {'dev': 'hasepfe:10000/p21/motor/fe.33', 'attr': 'position'},
                  'ps2off': {'dev': 'hasepfe:10000/p21/motor/fe.36', 'attr': 'position'},
                  'ps2gap': {'dev': 'hasepfe:10000/p21/motor/fe.35', 'attr': 'position'},
                  'ps2in': {'dev': 'hasepfe:10000/p21/motor/fe.37', 'attr': 'position'},
                  'ps2out': {'dev': 'hasepfe:10000/p21/motor/fe.38', 'attr': 'position'},
                  }
Styles = {'ps1off': {'dev': 'hasepfe:10000/p21/motor/fe.34', 'attr': 'position', 'widgetStyle': 'full'},
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

EH3slits = {'top': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u2.01', 'attr': 'position'},
            'bottom': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u2.02', 'attr': 'position'},
            'in': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u2.03', 'attr': 'position'},
            'out': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u2.04', 'attr': 'position'},
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

Experiment_old = {'LKM_T': {'dev': 'hasep212lkam:10000/p212/linkamt96/01', 'attr': 'Temperature', 'format': '.1f', 'widgetStyle': 'frame'},
              'LKM_target': {'dev': 'hasep212lkam:10000/p212/linkamt96/01', 'attr': 'TargetTemperature', 'format': '.1f', 'widgetStyle': 'frame'},
              'LKM_rate': {'dev': 'hasep212lkam:10000/p212/linkamt96/01', 'attr': 'HeatingRate', 'format': '.1f', 'widgetStyle': 'frame'},
              }

Experiment = {'symtx': {'dev': 'hasep21eh3:10000/symetrie/hexapod/main', 'attr': 'Tx'},
              'symty': {'dev': 'hasep21eh3:10000/symetrie/hexapod/main', 'attr': 'Ty'},
              'symtz': {'dev': 'hasep21eh3:10000/symetrie/hexapod/main', 'attr': 'Tz'},
              'temp': {'dev': 'hasep212lkam:10000/p212/linkamt96/01', 'attr': 'Temperature', 'format': '.1f'},
              'D_linear': {'dev': 'hasep21eh3:10000/p21/ofttmotor/linear', 'attr': 'Position'},
              'D_rot': {'dev': 'hasep21eh3:10000/p21/ofttmotor/bottom', 'attr': 'Position'},
              'D_load': {'dev': 'hasep21eh3:10000/p21/ofttloadcell/tension', 'attr': 'Load', 'format': '.1f'},
              'D_torsion': {'dev': 'hasep21eh3:10000/p21/ofttloadcell/torsion', 'attr': 'Load', 'format': '.1f'},
             }



symmetrie = {}

Server = {'Keithley': {'server': 'Keithley2602b/eh3_1'},
          }

Sweep_stuff = {'M_pilc': {'dev': 'hasep21eh3:10000/p21/pilcarraybasedtg2/eh3.01', 'attr': 'Arm', 'format': 'd'},
               'S_pilc': {'dev': 'hasep21eh3:10000/p21/pilcarraybasedtg2slave/eh3.01', 'attr': 'Arm', 'format': 'd'}
              }
InDaBeam = {'OH xeye': {'property': ('EYES', 'oh2'), 'host': 'hasep212oh'},
            'EH xeye': {'property': ('EYES', 'eh3'), 'host': 'hasep212oh'},
}


