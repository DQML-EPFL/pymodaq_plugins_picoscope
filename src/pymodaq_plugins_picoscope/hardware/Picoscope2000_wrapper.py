# -*- coding: utf-8 -*-
"""
Created on Mon Feb 3 2025

@author: dqml-lab
"""

import ctypes
import numpy as np
from picosdk.ps2000 import ps2000 as ps
from picosdk.functions import adc2mV, assert_pico2000_ok, mV2adc
from math import *


class Picoscope_Wrapper:

    ############## My methods

    def __init__(self, aquire_time=.5, sampling_freq=0.20, trigger=500, trigger_chan=1) -> None:
        """
        Max Sampling Freq = 80 MHz
        """
        self.aquire_time = aquire_time
        self.num_points = sampling_freq * 1e6 *aquire_time 
        self.sampling_frequency = sampling_freq
    
        self.preTriggerSamples = 100
        self.postTriggerSamples = int( self.num_points - self.preTriggerSamples)
        self.trigger_chan_number = trigger_chan

        self.maxSamples = int(self.preTriggerSamples + self.postTriggerSamples)
        self.timebase = int( 80/sampling_freq - 1 )  # Page 24 of PG
        self.timebase = 8 # As per exemple for now

        self.chandle = ctypes.c_int16()
        self.status = {}
        self.maxADC = ctypes.c_int16(32767)

        self.timeIntervalns = None

        self.trigger_threshold = trigger  # mV
        self.bufferA = None
        self.bufferB = None
        self.chARange = None
        self.chBRange = None
        
        print()
        print("----- Setting up Picoscope with parameters : ")
        print("Aquire Time = ", aquire_time, "s")
        print("Sampling Frequency = ", 80 / (self.timebase+1), "MHz,  Step size = ", (self.timebase+1)*12.5, " ns" )
        print("Total Points = ", self.maxSamples)
        print("Timebase = ", self.timebase)
        print("----------")
        print()

        self.initialize_picoscope()


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
        self.chARange = PS2000_2V = 7
        self.status["setChA"] = ps.ps2000_set_channel(handle, channel, enabled, coupling_type, self.chARange)
        assert_pico2000_ok(self.status["setChA"])

        # ----- Set up channel B
        handle = self.chandle
        channel = PS2000_CHANNEL_B = 1
        enabled = 1
        coupling_type = PS2000_DC = 1
        self.chBRange = PS2000_2V = 7
        self.status["setChB"] = ps.ps2000_set_channel(handle, channel, enabled, coupling_type, self.chBRange)
        assert_pico2000_ok(self.status["setChB"])

        # ----- Set up simple Trigger
        handle = self.chandle
        source = PS2000_CHANNEL_B = 1
        threshold = mV2adc(self.trigger_threshold, self.chBRange, self.maxADC) # 1024 ADC counts
        direction = PS2000_RISING = 0
        delay = 0 # s
        autoTrigger_ms = 100
        self.status["trigger"] = ps.ps2000_set_simple_trigger(handle, source, threshold, direction, delay, autoTrigger_ms )
        assert_pico2000_ok(self.status["trigger"])

        
        # Set number of pre and post trigger samples to be collected
        preTriggerSamples = 1000
        postTriggerSamples = 1000
        self.maxSamples = preTriggerSamples + postTriggerSamples

        # ----- Setup Timebase
        timeInterval = ctypes.c_int32()
        timeUnits = ctypes.c_int32()
        oversample = ctypes.c_int16(1)
        maxSamplesReturn = ctypes.c_int32()

        handle = self.chandle
        self.timebase = self.timebase
        noSamples = self.maxSamples
        pointer_to_timeInterval = ctypes.byref(timeInterval)
        pointer_to_timeUnits = ctypes.byref(timeUnits)
        self.oversample = oversample
        pointer_to_maxSamples = ctypes.byref(maxSamplesReturn)

        self.status["getTimebase2"] = ps.ps2000_get_timebase(handle, self.timebase, noSamples, pointer_to_timeInterval, pointer_to_timeUnits, oversample, pointer_to_maxSamples)
        assert_pico2000_ok(self.status["getTimebase2"])

        # # ----------
        # # Setup Memory and Buffers
        # # ----------

        # # ----- Set  up memory segments
        # handle = self.chandle
        # nSegments = 10
        # nMaxSamples = ctypes.c_int32(0)
        # self.status["setMemorySegments"] = ps.ps2000MemorySegments(self.chandle, 10, ctypes.byref(nMaxSamples))
        # assert_pico2000_ok(self.status["setMemorySegments"])

        # # ----- Set number of captures
        # handle = self.chandle
        # nCaptures = 1
        # self.status["SetNoOfCaptures"] = ps.ps2000SetNoOfCaptures(handle, nCaptures)
        # assert_pico2000_ok(self.status["SetNoOfCaptures"])

        # # ----- Create buffers
        # self.bufferA = (ctypes.c_int16 * self.maxSamples)()
        # self.bufferB = (ctypes.c_int16 * self.maxSamples)()

        # # ----- Assign buffers
        # handle = self.chandle
        # channelA = PS2000_CHANNEL_A = 0
        # channelB = PS2000_CHANNEL_B = 1
        # bufferLength = self.maxSamples
        # mode = PS2000_RATIO_MODE_NONE = 0

        # self.status["setDataBufferA"] = ps.ps2000SetDataBuffer(handle, PS2000_CHANNEL_A, ctypes.byref(self.bufferA), bufferLength)
        # self.status["setDataBufferB"] = ps.ps2000SetDataBuffer(handle, PS2000_CHANNEL_B, ctypes.byref(self.bufferB), bufferLength)



    ############## PMD mandatory methods

    def get_the_x_axis(self):
        print("Tut")
        return 0
        # return self.data_transfer.time_data().magnitude


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
        no_values = ctypes.c_int32(self.maxSamples)

        self.status["getValues"] = ps.ps2000_get_values(self.chandle, pointer_to_bufferA, pointer_to_bufferB, None, None, pointer_to_oversample, no_values)
        assert_pico2000_ok(self.status["getValues"])

        # # convert from adc to mV
        channelA_data =  adc2mV(self.bufferA, self.chARange, self.maxADC)
        channelB_data =  adc2mV(self.bufferB, self.chBRange, self.maxADC)

        # Create time data
        time = np.linspace(0, ((no_values.value)-1) * self.timeIntervalns.value * 1e-9, no_values.value)

        return time, [np.array(channelA_data), np.array(channelB_data)]

    def set_timebase(self, aquire_time=None, sampling_freq=None):
        if aquire_time: self.num_points = self.sampling_frequency*1e6 *aquire_time
        elif sampling_freq: self.num_points = sampling_freq*1e6 *self.aquire_time

        self.postTriggerSamples = int( self.num_points - self.preTriggerSamples)
        self.maxSamples = int(self.preTriggerSamples + self.postTriggerSamples)


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
            #if not exit(manager, *sys.exc_info()):

                #raise
        #finally:
        #    if not hit_except:
        #        exit(manager)
        #        manager.close()


if __name__=="__main__":

    pico = Picoscope_Wrapper(aquire_time=.5, 
                             sampling_freq=0.20, 
                             trigger=500, 
                             trigger_chan=1)
    
    time, data = pico.start_a_grab_snap()

    data_A = data[0]
    data_B = data[1]

    import matplotlib.pyplot as plt
    plt.plot(time, data_A)
    plt.plot(time, data_B)
    plt.show()