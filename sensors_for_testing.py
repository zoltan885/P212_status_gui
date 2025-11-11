#sensors.py



####################   TANGO SENSORS   ####################
attrs_VME = ['Acceleration', 'BaseRate', 'Conversion', 'SettleTime', 'SlewRate', 'SlewRateMax', 'SlewRateMin', 'StepBacklash', \
            'UnitBacklash', 'UnitCalibration', 'UnitLimitMax', 'UnitLimitMin', 'CwLimit', 'CcwLimit', 'Position', 'AccuLimitMin',\
            'ConversionEncoder', 'PositionEncoder', 'Status']  # 19 attributes

tango_sensors = [{'type': 'Tango',
        'address': f'hasep21eh2:10000/p21/motor/eh2_u1.{d:02d}',
        'attribute': attr,
        'display_name': f'eh2_u1.{d:02d} {attr}'
    } for d in range(15, 16) for attr in attrs_VME]



#####################   TINE SENSORS   ####################

tine_sensors = [
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/PU21b',
        'property': 'Undulator.Gap',
        'display_name': 'PU21b Gap'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/PU07',
        'property': 'Undulator.Gap',
        'display_name': 'PU07 Gap'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/P1max',
        'property': 'P21.Druck',
        'display_name': 'P1max Pressure'
    },
    {
        'type': 'Tine',
        'address': 'PETRA/HISTORY/ITR_Mono_B',
        'property': 'P21.Druck',
        'display_name': 'P2max Pressure'
    },

]