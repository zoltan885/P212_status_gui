#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

frontend = {'ps1off': 'hasepfe:10000/p21/motor/fe.34',
            'ps1gap': 'hasepfe:10000/p21/motor/fe.33',
            'ps2off': 'hasepfe:10000/p21/motor/fe.36',
            'ps2gap': 'hasepfe:10000/p21/motor/fe.35',
            'ps2in': 'hasepfe:10000/p21/motor/fe.37',
            'ps2out': 'hasepfe:10000/p21/motor/fe.38',
            }
undulator = {'gap': {'dev': 'hasep212oh:10000/p21/plcundulator/oh.01', 'attr': 'CurrentGap'},
             }

mots = {'hury': 'hasep212oh:10000/p21/motor/oh_u3.04',
        'hdry': 'hasep212oh:10000/p21/motor/oh_u3.06',
        'hutz': 'hasep212oh:10000/p21/motor/oh_u3.03',
        'hdtz': 'hasep212oh:10000/p21/motor/oh_u3.05',
        'hus ':  'hasep212oh:10000/p21/motor/oh_u3.02',
        'hds ':  'hasep212oh:10000/p21/motor/oh_u3.09',
        'hud ':  'hasep212oh:10000/p21/motor/oh_u4.11',
        }

ctrs = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent'},
        }

props = {'foil': {'property': ('FOILS', 'current_foil')},
         'energy': {'property': ('GLOBAL', 'ENERGY')},
         'absorber': {'property': ('GLOBAL', 'ABSORBER')},
         }
