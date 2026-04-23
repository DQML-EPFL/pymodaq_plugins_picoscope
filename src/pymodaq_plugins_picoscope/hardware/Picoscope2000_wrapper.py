# -*- coding: utf-8 -*-
"""
Created on Mon Feb 3 2025

@author: dqml-lab
"""

# https://www.picotech.com/download/manuals/picoscope-2000-series-programmers-guide.pdf

import ctypes
import numpy as np
from picosdk.ps2000 import ps2000 as ps
from picosdk.functions import adc2mV, assert_pico2000_ok, mV2adc
from math import *


class Picoscope_Wrapper:

    ############## My methods

    def __init__(self, aquire_time=.5, sampling_freq=0.20, trigger=500, trigger_chan=1, voltage_range=6) -> None:
        """
        Max Sampling Freq = 80 MHz
        """

        print("========= Initializing Picoscope ================")

        self.desired_sampling_freq = sampling_freq
        self.aquire_time = aquire_time

        self.timebase = self.get_closest_timebase()
        self.maxSamples = self.get_numSamples()

        self.trigger_chan_number = trigger_chan
        self.preTriggerSamples = 100
        self.postTriggerSamples = self.maxSamples - self.preTriggerSamples

        self.voltage_range = voltage_range

        self.chandle = ctypes.c_int16()
        self.status = {}
        self.maxADC = ctypes.c_int16(32767)

        self.trigger_threshold = trigger  # mV
        self.bufferA = None
        self.bufferB = None
        self.chARange = None
        self.chBRange = None

        self.initialize_picoscope()


        print(f"Sampling Frequency : Desired {sampling_freq:.2f} MHz - Real {self.real_sampling_freq} MHz   ( timebase : {self.timebase} )")
        print(f"Aquire Time : Desired {aquire_time*1e3:.2f} ms - Real {self.maxSamples * self.dt * 1e3:.2f} ms  ( Number of Samples : {self.desired_num_sample}, max 3900)")
        print("=================================================")


    def __del__(self):
        print("Stopping Picoscope")
        
        # Stop the scope
        handle = self.chandle
        self.status["stop"] = ps.ps2000_stop(handle)
        assert_pico2000_ok(self.status["stop"])

        # Close unit / Disconnect the scope
        handle = self.chandle
        self.status["close"] = ps.ps2000_close_unit(handle)
        assert_pico2000_ok(self.status["close"])


    def initialize_picoscope(self):

        # ----------
        # Initialise Device
        # ----------

        # Open 2000 series PicoScope
        # Returns handle to chandle for use in future API functions
        self.status["openUnit"] = ps.ps2000_open_unit()
        assert_pico2000_ok(self.status["openUnit"])

        self.chandle = ctypes.c_int16(self.status["openUnit"])


        # ----------
        # Setup Channels, Trigger, Time
        # ----------

        # ----- Set up channel A
        handle = self.chandle
        channel = PS2000_CHANNEL_A = 0
        enabled = 1
        coupling_type = PS2000_DC = 1
        self.chARange = self.voltage_range
        self.status["setChA"] = ps.ps2000_set_channel(handle, channel, enabled, coupling_type, self.chARange)
        assert_pico2000_ok(self.status["setChA"])

        # ----- Set up channel B
        handle = self.chandle
        channel = PS2000_CHANNEL_B = 1
        enabled = 1
        coupling_type = PS2000_DC = 1
        self.chBRange = self.voltage_range
        self.status["setChB"] = ps.ps2000_set_channel(handle, channel, enabled, coupling_type, self.chBRange)
        assert_pico2000_ok(self.status["setChB"])

        # ----- Set up simple Trigger
        handle = self.chandle
        source = PS2000_CHANNEL_B = 1
        threshold = mV2adc(self.trigger_threshold, self.chBRange, self.maxADC) # 1024 ADC counts
        direction = PS2000_RISING = 0
        delay = 0 # s
        autoTrigger_ms = 100
        self.status["trigger"] = ps.ps2000_set_trigger(handle, source, threshold, direction, delay, autoTrigger_ms )
        assert_pico2000_ok(self.status["trigger"])


        # ----- Setup Timebase
        self.timeInterval = ctypes.c_int32()
        timeUnits = ctypes.c_int32()
        oversample = ctypes.c_int16(1)
        maxSamplesReturn = ctypes.c_int32()

        handle = self.chandle
        timebase = self.timebase
        noSamples = self.maxSamples
        pointer_to_timeInterval = ctypes.byref(self.timeInterval)
        pointer_to_timeUnits = ctypes.byref(timeUnits)
        self.oversample = oversample
        pointer_to_maxSamples = ctypes.byref(maxSamplesReturn)

        self.status["getTimebase"] = ps.ps2000_get_timebase(handle, timebase, noSamples, pointer_to_timeInterval, pointer_to_timeUnits, oversample, pointer_to_maxSamples)
        assert_pico2000_ok(self.status["getTimebase"])


    def get_the_x_axis(self):
        time = np.linspace(0, ((self.no_values.value)-1) * self.timeInterval.value * 1e-9, self.no_values.value)
        return time


    def start_a_grab_snap(self):

        # ----------
        # Get Data
        # ----------

        # ----- Run Block Capture
        # This will continue to run until buffer is full
        TimeIndisposed_ms = ctypes.c_int32()

        handle = self.chandle
        noSamples = self.maxSamples
        timebase = self.timebase
        oversample = self.oversample
        pointer_to_TimeIndisposed_ms = ctypes.byref(TimeIndisposed_ms)
        self.status["runBlock"] = ps.ps2000_run_block(handle, noSamples, timebase, oversample, pointer_to_TimeIndisposed_ms)
        assert_pico2000_ok(self.status["runBlock"])


        # --- Check for end of capture
        ready = ctypes.c_int16(0)
        check = ctypes.c_int16(0)
        while ready.value == check.value:
            self.status["isReady"] = ps.ps2000_ready(self.chandle)
            ready = ctypes.c_int16(self.status["isReady"])


        # Create buffers ready for data
        bufferA = (ctypes.c_int16 * self.maxSamples)()
        bufferB = (ctypes.c_int16 * self.maxSamples)()

        # ---- Collect data from buffer
        handle = self.chandle
        pointer_to_bufferA = ctypes.byref(bufferA)
        pointer_to_bufferB = ctypes.byref(bufferB)
        pointer_to_oversample = ctypes.byref(self.oversample)
        self.no_values = ctypes.c_int32(self.maxSamples)

        self.status["getValues"] = ps.ps2000_get_values(self.chandle, pointer_to_bufferA, pointer_to_bufferB, None, None, pointer_to_oversample, self.no_values)
        assert_pico2000_ok(self.status["getValues"])

        # # convert from adc to mV
        channelA_data =  adc2mV(bufferA, self.chARange, self.maxADC)
        channelB_data =  adc2mV(bufferB, self.chBRange, self.maxADC)

        # Create time data
        time = np.linspace(0, ((self.no_values.value)-1) * self.timeInterval.value * 1e-9, self.no_values.value)

        return time, [np.array(channelA_data), np.array(channelB_data)]



    def stop(self):
        # Stop the scope
        self.status["stop"] = ps.ps2000_stop(self.chandle)
        assert_pico2000_ok(self.status["stop"])  

        # Close unitDisconnect the scope
        self.status["close"] = ps.ps2000_close_unit(self.chandle)
        assert_pico2000_ok(self.status["close"])
        # handle = chandle
        self.status["close"] = ps.ps2000_close_unit(self.chandle)
        assert_pico2000_ok(self.status["close"])


    def terminate_the_communication(self, manager, hit_except):
        try:
            print('Communication terminated')
            exit(manager)
            manager.close()

        except:
            hit_except = True


    def get_closest_timebase(self):
        shortest_dt = 10e-9           # 10 ns

        estimate_dt = 1 / (self.desired_sampling_freq*1e6)
        timebase = round( log2(estimate_dt / shortest_dt) )
        self.dt = shortest_dt * 2**timebase
        self.real_sampling_freq = (1 / self.dt ) *1e-6
        
        return timebase

    def get_numSamples(self):
        
        shortest_dt = 10e-9
        dt = shortest_dt * 2**self.timebase
        self.desired_num_sample = int(self.aquire_time / dt)

        if self.desired_num_sample>3900: print(f"==== Trace duration exceeds what is possible with this sampling frequency : {self.desired_num_sample} > 3900")
        return min(self.desired_num_sample, 3900)



if __name__=="__main__":

    pico = Picoscope_Wrapper(aquire_time=.01, 
                            sampling_freq=5, 
                            trigger=500, 
                            trigger_chan=1, 
                            voltage_range=5)
    
    time, data = pico.start_a_grab_snap()

    data_A = data[0]
    data_B = data[1]

    import matplotlib.pyplot as plt
    print(f"Duration : {time[-1]-time[0]}")
    print(f"Samplign freq : {len(data_A)/(time[-1]-time[1]) * 1e-6 } MHz" )
    print(f"Step : {(time[1]-time[0])*1e6} us")
    plt.plot(time, data_A)
    plt.plot(time, data_B)
    plt.show()