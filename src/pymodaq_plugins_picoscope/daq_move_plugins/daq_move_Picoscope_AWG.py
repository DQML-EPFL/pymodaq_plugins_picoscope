import numpy as np
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataToExport
from pymodaq.control_modules.move_utility_classes import (
    DAQ_Move_base, comon_parameters_fun, main, DataActuatorType, DataActuator
)
from pymodaq.utils.parameter import Parameter
from ..hardware.Picoscope2000_wrapper import Picoscope_Wrapper as Picoscope_Wrapper2000



class DAQ_Move_Picoscope_AWG(DAQ_Move_base):
    """
    PyMoDAQ DAQ_Move plugin to control the PicoScope 2204A built-in AWG.
    The 'position' axis is mapped to frequency (Hz).
    Waveform type, amplitude and offset are set via parameters.
    """

    _controller_units = 'Hz'
    is_multiaxes = False
    _axis_names = ['Frequency']
    _epsilon = 0.01  # Hz resolution

    params = comon_parameters_fun() + [
        {
            'title': 'AWG Settings',
            'name': 'awg_settings',
            'type': 'group',
            'children': [
                {
                    'title': 'Wave Type',
                    'name': 'wave_type',
                    'type': 'list',
                    'limits': {
                        'Sine': 0,
                        'Square': 1,
                        'Triangle': 2,
                        'DC': 3,
                        'Ramp Up': 4,
                        'Ramp Down': 5,
                    },
                    'value': 0
                },
                {
                    'title': 'Frequency (Hz)',
                    'name': 'frequency',
                    'type': 'float',
                    'value': 1000.0,
                    'min': 0.0,
                    'max': 100_000.0
                },
                {
                    'title': 'Amplitude pk-pk (mV)',
                    'name': 'amplitude_mv',
                    'type': 'float',
                    'value': 2000.0,    # 2V pk-pk
                    'min': 0.0,
                    'max': 4000.0
                },
                {
                    'title': 'Offset (mV)',
                    'name': 'offset_mv',
                    'type': 'float',
                    'value': 0.0,
                    'min': -2000.0,
                    'max': 2000.0
                },
                {
                    'title': 'Output Enabled',
                    'name': 'output_enabled',
                    'type': 'bool',
                    'value': False
                },
            ]
        }
    ]

    def ini_attributes(self):
        self.controller: Picoscope_Wrapper2000 = None

    def get_actuator_value(self):
        # WRONG - don't return DataActuator, PyMoDAQ wraps it itself
        # return DataActuator(data=freq)
        
        # CORRECT - return a plain float
        freq = self.settings.child('awg_settings', 'frequency').value()
        return freq

    def ini_detector(self, controller=None):
        # Reuse existing controller if slave, else open a new one
        if self.is_master:
            self.controller = Picoscope_Wrapper2000(
                aquire_time=0.01,
                sampling_freq=0.1,
                voltage_range=6,
                trigger=False,
                trigger_chan='B',
                trigger_level_mv=500
            )
        else:
            self.controller = controller

        info = "PicoScope AWG initialized"
        initialized = True
        return info, initialized
    
    def ini_stage(self, controller=None):
        if self.is_master:
            self.controller = Picoscope_Wrapper2000(
                aquire_time=0.01,
                sampling_freq=0.1,
                voltage_range=6,
                trigger=False,
                trigger_chan='B',
                trigger_level_mv=500
            )
        else:
            self.controller = controller

        info = "PicoScope AWG initialized"
        initialized = True
        return info, initialized
    
    def ini_stage(self, controller=None):
        if self.is_master:
            self.controller = Picoscope_Wrapper2000(
                aquire_time=0.01,
                sampling_freq=0.1,
                voltage_range=6,
                trigger=500,        # was trigger_level_mv=500
                trigger_chan=1,     # was trigger_chan='B' — this wrapper expects int
            )
        else:
            self.controller = controller

        info = "PicoScope AWG initialized"
        initialized = True
        return info, initialized

    def close(self):
        if self.is_master:
            self.controller.__del__()


    def move_rel(self, value):
        current = self.get_actuator_value()
        new_freq = max(0.0, current + float(value))
        self.move_abs(new_freq)

    def move_home(self):
        self.move_abs(1000.0)
    def commit_settings(self, param: Parameter):
        """Re-apply AWG settings whenever any parameter changes."""
        print(f"\n[COMMIT_SETTINGS] param changed: '{param.name()}' = {param.value()}")
        
        freq = self.settings.child('awg_settings', 'frequency').value()
        print(f"[COMMIT_SETTINGS] current freq from settings: {freq}")

        if param.name() == 'output_enabled':
            if not param.value():
                print("[COMMIT_SETTINGS] Output disabled → stopping sig gen")
                self.controller.stop_sig_gen()
                return
            else:
                print("[COMMIT_SETTINGS] Output enabled → applying settings")

        self._apply_awg_settings(freq)


    def _apply_awg_settings(self, freq_hz: float):
        enabled = self.settings.child('awg_settings', 'output_enabled').value()
        if not enabled:
            print("[APPLY_AWG] Output is OFF → skipping")
            return

        wave_type_raw = self.settings.child('awg_settings', 'wave_type').value()
        print(f"[APPLY_AWG] wave_type_raw={wave_type_raw!r} (type: {type(wave_type_raw).__name__})")

        # Handle both string key and int value from PyMoDAQ list param
        wave_type_map = {'Sine': 0, 'Square': 1, 'Triangle': 2, 'DC': 3, 'Ramp Up': 4, 'Ramp Down': 5}
        if isinstance(wave_type_raw, str):
            wave_type = wave_type_map[wave_type_raw]
        else:
            wave_type = int(wave_type_raw)

        amp_mv    = self.settings.child('awg_settings', 'amplitude_mv').value()
        offset_mv = self.settings.child('awg_settings', 'offset_mv').value()
        pk2pk_uv  = int(amp_mv * 1000)
        offset_uv = int(offset_mv * 1000)

        print(f"[APPLY_AWG] → wave={wave_type}, freq={freq_hz}Hz, amp={amp_mv}mV, offset={offset_mv}mV")

        self.controller.setup_sig_gen(
            wave_type=wave_type,
            freq_hz=freq_hz,
            pk2pk_uv=pk2pk_uv,
            offset_uv=offset_uv
        )
        print("[APPLY_AWG] setup_sig_gen call completed")


    def move_abs(self, value):
        freq = float(value)
        print(f"\n[MOVE_ABS] requested freq={freq}Hz")
        self.settings.child('awg_settings', 'frequency').setValue(freq)
        self._apply_awg_settings(freq)
        self.emit_status(ThreadCommand('Update_Status', [f'AWG freq set to {freq:.1f} Hz']))



if __name__ == '__main__':
    main(__file__)