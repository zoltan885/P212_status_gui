#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 10:21:49 2024

@author: hegedues
"""

grouping = {
    'tabs': {
        'Optical Hutch': {
            'scroll1': ['mots',
                        'ctrs',
                        'more_ctrs',
                        ],
        },
    },
}



ctrs = {'curr up': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentA', 'format': '.2e', 'widgetStyle': 'background'},
        'curr mid': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
        'curr down': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3_1.01', 'attr': 'measCurrent',  'format': '.2e', 'widgetStyle': 'background'},
        }

mots = {'01': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u4.10', 'attr': 'position'},
        '02': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u4.11', 'attr': 'position'},
        '03': {'dev': 'hasep21eh3:10000/p21/motor/eh3_u4.12', 'attr': 'position'},
        }

more_ctrs = {'curr001': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentB', 'format': '.2e', 'widgetStyle': 'background'},
             'curr002': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentC', 'format': '.2e', 'widgetStyle': 'background'},
             'curr003': {'dev': 'hasep21eh3:10000/p21/tetramm/hasep212tetra01', 'attr': 'CurrentD', 'format': '.2e', 'widgetStyle': 'background'},
             'curr004': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3.01', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
             'curr005': {'dev': 'hasep21eh3:10000/p21/keithley2602b/eh3.02', 'attr': 'measCurrent', 'format': '.2e', 'widgetStyle': 'background'},
        }
