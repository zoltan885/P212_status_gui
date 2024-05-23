#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

visible = ['frontend', 'undulator', 'mots', 'ctrs', 'props']

frontend = {'ps1off': {'dev': 'hasepfe:10000/p21/motor/fe.34', 'attr': 'position', 'compact': False},
            'ps1gap': {'dev': 'hasepfe:10000/p21/motor/fe.33', 'attr': 'position'},
            'ps2off': {'dev': 'hasepfe:10000/p21/motor/fe.36', 'attr': 'position'},
            'ps2gap': {'dev': 'hasepfe:10000/p21/motor/fe.35', 'attr': 'position'},
            'ps2in': {'dev': 'hasepfe:10000/p21/motor/fe.37', 'attr': 'position'},
            'ps2out': {'dev': 'hasepfe:10000/p21/motor/fe.38', 'attr': 'position'},
            }
undulator = {'gap': {'dev': 'hasep212oh:10000/p21/plcundulator/oh.01', 'attr': 'CurrentGap', 'format': '.0f'},
             }

mots = {'hury': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.04', 'attr': 'position'},
        'hdry': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.06', 'attr': 'position'},
        'hutz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.03', 'attr': 'position'},
        'hdtz': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.05', 'attr': 'position'},
        'hus ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.02', 'attr': 'position'},
        'hds ': {'dev': 'hasep212oh:10000/p21/motor/oh_u3.09', 'attr': 'position'},
        'hud ': {'dev': 'hasep212oh:10000/p21/motor/oh_u4.11', 'attr': 'position'},
        }

ctrs = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.3e'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.3e'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.3e'},
        }

props = {'foil': {'property': ('FOILS', 'current_foil'), 'host': 'hasep212oh'},
         'energy': {'property': ('GLOBAL', 'ENERGY'), 'host': 'hasep212oh'},
         'absorber': {'property': ('GLOBAL', 'ABSORBER'), 'host': 'hasep212oh'},
         }
