#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 23 09:37:10 2024

@author: hegedues
"""
import numpy as np

# Si lattice parameter at RT
ASIRT = 5.43102  # @ 22.5 C


def EToAngle(energy, unit='urad'):
    '''
    converts the energy [keV] to angle [urad or degree] (depending on the unit kw) (for Si 111 reflection)
    '''
    assert unit in ['degree', 'urad'], 'Invalid unit'
    dSi111 = ASIRT/np.sqrt(3.)
    wavelength = 12.39842/float(energy)
    theta = np.arcsin(wavelength/(2.0 * dSi111))
    if unit == 'urad':
        return 1e6*theta
    if unit == 'degree':
        return 180/np.pi*theta


def AngleToE(angle, unit='urad'):
    '''
    converts the angle [urad or degree] (depending on the unit kw) to energy [keV] (for Si 111 reflection)
    '''
    assert unit in ['degree', 'urad'], 'Invalid unit'
    dSi111 = ASIRT/np.sqrt(3)
    if unit == 'urad':
        return 12.39842/(np.sin(1e-6*angle)*2*dSi111)
    if unit == 'degree':
        return 12.39842/(np.sin(angle/180*np.pi)*2*dSi111)
