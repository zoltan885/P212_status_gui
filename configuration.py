#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

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

props = {'foil': {'property': ('FOILS', 'upstream_counter')},
         'energy': {'property': ('GLOBAL', 'ENERGY')},
         'absorber': {'property': ('GLOBAL', 'ABSORBER')},
         }
