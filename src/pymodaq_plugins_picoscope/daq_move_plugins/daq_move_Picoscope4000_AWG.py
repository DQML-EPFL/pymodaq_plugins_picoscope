import numpy as np
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataToExport
from pymodaq.control_modules.move_utility_classes import (
    DAQ_Move_base, comon_parameters_fun, main, DataActuatorType, DataActuator
)
from pymodaq.utils.parameter import Parameter
from ..hardware.Picoscope4000_wrapper import Picoscope_Wrapper as Picoscope_Wrapper4000


class DAQ_Move_Picoscope4000_AWG(DAQ_Move_base):
    """
    PyMoDAQ DAQ_Move plugin for the PicoScope 4000 series built-in AWG.
    Position axis = frequency (Hz).
    """

    _controller_units = 'Hz'
    is_multiaxes = False
    _axis_names = ['Frequency']
    _epsilon = 0.01

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
                        'Ramp Up': 3,
                        'Ramp Down': 4,
                        'Sinc': 5,
                        'Gaussian': 6,
                        'Half Sinc': 7,
                        'DC Voltage (use offset)': 8,
                    },
                    'value': 0
                },
                {
                    'title': 'Frequency (Hz)',
                    'name': 'frequency',
                    'type': 'float',
                    'value': 1000.0,
                    'min': 0.0,
                    'max': 1_000_000.0   # ps4000 goes up to ~1MHz depending on model
                },
                {
                    'title': 'Amplitude pk-pk (mV)',
                    'name': 'amplitude_mv',
                    'type': 'float',
                    'value': 2000.0,
                    'min': 0.0,
                    'max': 2000.0
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
        self.controller: Picoscope_Wrapper4000 = None

    def get_actuator_value(self):
        return self.settings.child('awg_settings', 'frequency').value()

    def ini_stage(self, controller=None):
        if self.is_master:
            self.controller = Picoscope_Wrapper4000(
                aquire_time=0.01,
                sampling_freq=0.2,
                trigger=500,
                trigger_chan=1
            )
        else:
            self.controller = controller

        info = "PicoScope 4000 AWG initialized"
        return info, True

    def close(self):
        if self.is_master:
            self.controller.__del__()

    def move_abs(self, value):
        freq = float(value)
        print(f"\n[MOVE_ABS 4000] requested freq={freq}Hz")
        self.settings.child('awg_settings', 'frequency').setValue(freq)
        self._apply_awg_settings(freq)
        self.emit_status(ThreadCommand('Update_Status', [f'AWG freq set to {freq:.1f} Hz']))

    def move_rel(self, value):
        current = self.get_actuator_value()
        new_freq = max(0.0, current + float(value))
        self.move_abs(new_freq)

    def move_home(self):
        self.move_abs(1000.0)

    def commit_settings(self, param: Parameter):
        print(f"\n[COMMIT_SETTINGS 4000] '{param.name()}' = {param.value()}")
        freq = self.settings.child('awg_settings', 'frequency').value()

        if param.name() == 'output_enabled':
            if not param.value():
                print("[COMMIT_SETTINGS 4000] Output disabled → stopping")
                self.controller.stop_sig_gen()
                return
            else:
                print("[COMMIT_SETTINGS 4000] Output enabled → applying")

        self._apply_awg_settings(freq)
    """
    def _apply_awg_settings(self, freq_hz: float):
        enabled = self.settings.child('awg_settings', 'output_enabled').value()
        if not enabled:
            print("[APPLY_AWG 4000] Output OFF → skipping")
            return

        wave_type_raw = self.settings.child('awg_settings', 'wave_type').value()
        print(f"[APPLY_AWG 4000] wave_type_raw={wave_type_raw!r} ({type(wave_type_raw).__name__})")

        wave_type_map = {
            'Sine': 0, 'Square': 1, 'Triangle': 2, 'DC Voltage': 3,
            'Ramp Up': 4, 'Ramp Down': 5, 'Sinc': 6, 'Gaussian': 7, 'Half Sinc': 8
        }
        wave_type = wave_type_map[wave_type_raw] if isinstance(wave_type_raw, str) else int(wave_type_raw)

        amp_mv    = self.settings.child('awg_settings', 'amplitude_mv').value()
        offset_mv = self.settings.child('awg_settings', 'offset_mv').value()
        pk2pk_uv  = int(amp_mv * 1000)
        offset_uv = int(offset_mv * 1000)

        print(f"[APPLY_AWG 4000] wave={wave_type}, freq={freq_hz}Hz, "
              f"amp={amp_mv}mV ({pk2pk_uv}uV), offset={offset_mv}mV ({offset_uv}uV)")

        self.controller.setup_sig_gen(
            wave_type=wave_type,
            freq_hz=freq_hz,
            pk2pk_uv=pk2pk_uv,
            offset_uv=offset_uv
        )
        print("[APPLY_AWG 4000] Done")
    """

    def _apply_awg_settings(self, freq_hz: float):
        enabled = self.settings.child('awg_settings', 'output_enabled').value()
        if not enabled:
            return

        wave_type_raw = self.settings.child('awg_settings', 'wave_type').value()
        wave_type_map = {
            'Sine': 0, 'Square': 1, 'Triangle': 2, 
            'Ramp Up': 3, 'Ramp Down': 4, 'Sinc': 5, 'Gaussian': 6, 'Half Sinc': 7,'DC Voltage': 8,
        }
        wave_type = wave_type_map[wave_type_raw] if isinstance(wave_type_raw, str) else int(wave_type_raw)

        amp_mv    = self.settings.child('awg_settings', 'amplitude_mv').value()
        offset_mv = self.settings.child('awg_settings', 'offset_mv').value()
        pk2pk_uv  = int(amp_mv * 1000)
        offset_uv = int(offset_mv * 1000)

        # Hardware constraint: signal must stay within ±1V
        # i.e. offset + pk2pk/2 <= 1_000_000 and offset - pk2pk/2 >= -1_000_000
        half_pk2pk_uv = pk2pk_uv // 2
        max_offset_uv =  1_000_000 - half_pk2pk_uv
        min_offset_uv = -1_000_000 + half_pk2pk_uv

        if offset_uv > max_offset_uv or offset_uv < min_offset_uv:
            clamped_uv = max(min_offset_uv, min(max_offset_uv, offset_uv))
            print(f"[APPLY_AWG] Offset clamped: {offset_uv} → {clamped_uv} µV "
                f"(pk2pk={pk2pk_uv} µV, headroom=±{max_offset_uv} µV)")
            offset_uv = clamped_uv
            # Update UI to reflect actual value
            self.settings.child('awg_settings', 'offset_mv').setValue(offset_uv / 1000.0)
            self.emit_status(ThreadCommand('Update_Status',
                [f'Offset clamped to {offset_uv/1000:.1f} mV — reduce amplitude for more range']))

        self.controller.setup_sig_gen(
            wave_type=wave_type,
            freq_hz=freq_hz,
            pk2pk_uv=pk2pk_uv,
            offset_uv=offset_uv
        )


if __name__ == '__main__':
    main(__file__)