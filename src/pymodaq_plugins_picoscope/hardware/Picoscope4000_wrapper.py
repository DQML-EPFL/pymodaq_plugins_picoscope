# -*- coding: utf-8 -*-
"""
Created on Mon Feb 3 2025

@author: dqml-lab
"""

import ctypes
import threading
import numpy as np
from picosdk.ps4000 import ps4000 as ps
from picosdk.functions import adc2mV, assert_pico_ok, mV2adc
from math import *


class Picoscope_Wrapper:

    ############## My methods
    """
    def __init__(self, aquire_time=.5, sampling_freq=0.20, trigger=500, trigger_chan=1) -> None:

        

        self.aquire_time = aquire_time
        self.num_points = sampling_freq*1e6 *aquire_time 
        self.sampling_frequency = sampling_freq
        self._lock = threading.Lock()
    
        self.preTriggerSamples = 100
        self.postTriggerSamples = int( self.num_points - self.preTriggerSamples)
        self.trigger_chan_number = trigger_chan

        self.maxSamples = int(self.preTriggerSamples + self.postTriggerSamples)
        self.timebase = int( 80/sampling_freq - 1 )  # Page 24 of PG

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
    """
    def _freq_mhz_to_timebase(self, freq_mhz: float) -> int:
        """PS4000 (this unit): dt = (tb + 1) * 100 ns, max 10 MHz."""
        dt_ns = 1000.0 / freq_mhz
        tb = round(dt_ns / 100.0) - 1
        tb = max(0, tb)  # clamp to valid range
        return tb
            
    def __init__(self, aquire_time=.5, sampling_freq=0.20, trigger=500, trigger_chan=1):
        self.aquire_time = aquire_time
        self.sampling_frequency = sampling_freq
        self.trigger_chan_number = trigger_chan
        self.trigger_threshold = trigger
        self._lock = threading.Lock()

        self.chandle = ctypes.c_int16()
        self.status = {}
        self.maxADC = ctypes.c_int16(32767)
        self.timeIntervalns = None
        self.bufferA = None
        self.bufferB = None
        self.chARange = 7
        self.chBRange = 7


        # Step 1: compute timebase from desired sampling freq
        #self.timebase = int(80 / sampling_freq - 1)
        self.timebase = self._freq_mhz_to_timebase(sampling_freq)
        print(f"Requested timebase: {self.timebase}")


        # Step 2: open scope and query the REAL time interval for this timebase
        self._open_and_setup_channels()   # open unit + set channels + trigger

        # Step 3: query real dt BEFORE computing maxSamples
        self.timeIntervalns = ctypes.c_float()
        returnedMaxSamples = ctypes.c_int32()
        oversample = ctypes.c_int16(1)
        # Use a large dummy sample count just to get the interval
        print(f"DEBUG: querying timebase {self.timebase} from hardware")

        
        self.status["getTimebase2"] = ps.ps4000GetTimebase2(
            self.chandle, self.timebase, 1000,
            ctypes.byref(self.timeIntervalns),
            oversample,
            ctypes.byref(returnedMaxSamples), 0
        )
        assert_pico_ok(self.status["getTimebase2"])
        print(f"DEBUG: hardware returned dt = {self.timeIntervalns.value} ns")

        real_dt_s = self.timeIntervalns.value * 1e-9
        real_fs_mhz = (1 / real_dt_s) * 1e-6

        # Step 4: compute maxSamples from REAL dt
        self.maxSamples = int(self.aquire_time / real_dt_s)
        self.preTriggerSamples = 100
        self.postTriggerSamples = self.maxSamples - self.preTriggerSamples

        print(f"Sampling Frequency: requested={sampling_freq} MHz, real={real_fs_mhz:.4f} MHz")
        print(f"dt real = {real_dt_s*1e6:.3f} µs")
        print(f"Acquire Time: requested={aquire_time*1e3:.2f} ms, "
            f"real={self.maxSamples * real_dt_s * 1e3:.3f} ms")
        print(f"maxSamples = {self.maxSamples}")

        # Step 5: finish setup with correct maxSamples
        self._setup_memory_and_buffers()


    def __del__(self):
        print("Stopping Picoscope")
        
        # Stop the scope
        handle = self.chandle
        self.status["stop"] = ps.ps4000Stop(handle)
        assert_pico_ok(self.status["stop"])

        # Close unit / Disconnect the scope
        handle = self.chandle
        self.status["close"] = ps.ps4000CloseUnit(handle)
        assert_pico_ok(self.status["close"])

    def _open_and_setup_channels(self):
        """Open unit, set channels and trigger."""
        self.status["openunit"] = ps.ps4000OpenUnit(ctypes.byref(self.chandle))
        try:
            assert_pico_ok(self.status["openunit"])
        except:
            powerStatus = self.status["openunit"]
            if powerStatus in (282, 286):
                self.status["changePowerSource"] = ps.ps4000ChangePowerSource(self.chandle, powerStatus)
                assert_pico_ok(self.status["changePowerSource"])
            else:
                raise

        # Channel A
        self.status["setChA"] = ps.ps4000SetChannel(self.chandle, 0, 1, 1, self.chARange)
        assert_pico_ok(self.status["setChA"])

        # Channel B
        self.status["setChB"] = ps.ps4000SetChannel(self.chandle, 1, 1, 1, self.chBRange)
        assert_pico_ok(self.status["setChB"])

        # Trigger
        """
        threshold = mV2adc(self.trigger_threshold, self.chBRange, self.maxADC)
        self.status["trigger"] = ps.ps4000SetSimpleTrigger(
            self.chandle, 1, self.trigger_chan_number,
            threshold, 2, 0, 1
        )
        assert_pico_ok(self.status["trigger"])
        """

        # ----- Set up simple Trigger
        handle = self.chandle
        enabled = 1
        # source = PS4000_CHANNEL_B
        source = self.trigger_chan_number
        threshold = mV2adc(self.trigger_threshold, self.chBRange, self.maxADC)
        direction = PS4000_RISING = 2
        delay = 0 # s
        autoTrigger_ms = 1 # ms  #TODO: Autotriggers after some time ?
        self.status["trigger"] = ps.ps4000SetSimpleTrigger(handle, enabled, source, threshold, direction, delay, autoTrigger_ms )
        assert_pico_ok(self.status["trigger"])

    def _setup_memory_and_buffers(self):
        """Set memory segments and allocate buffers — call AFTER maxSamples is known."""
        nMaxSamples = ctypes.c_int32(0)
        self.status["setMemorySegments"] = ps.ps4000MemorySegments(
            self.chandle, 10, ctypes.byref(nMaxSamples)
        )
        assert_pico_ok(self.status["setMemorySegments"])

        self.status["SetNoOfCaptures"] = ps.ps4000SetNoOfCaptures(self.chandle, 1)
        assert_pico_ok(self.status["SetNoOfCaptures"])

        self.bufferA = (ctypes.c_int16 * self.maxSamples)()
        self.bufferB = (ctypes.c_int16 * self.maxSamples)()

        self.status["setDataBufferA"] = ps.ps4000SetDataBuffer(
            self.chandle, 0, ctypes.byref(self.bufferA), self.maxSamples
        )
        self.status["setDataBufferB"] = ps.ps4000SetDataBuffer(
            self.chandle, 1, ctypes.byref(self.bufferB), self.maxSamples
        )

    def initialize_picoscope(self):

        # ----------
        # Initialise Device
        # ----------

        # Open 4000 series PicoScope
        # Returns handle to chandle for use in future API functions
        self.status["openunit"] = ps.ps4000OpenUnit(ctypes.byref(self.chandle))

        # Check power Status
        try:
            assert_pico_ok(self.status["openunit"])
        except: # PicoNotOkError:
            powerStatus = self.status["openunit"]

            if powerStatus == 286:
                self.status["changePowerSource"] = ps.ps4000ChangePowerSource(self.chandle, powerStatus)
            elif powerStatus == 282:
                self.status["changePowerSource"] = ps.ps4000ChangePowerSource(self.chandle, powerStatus)
            else:
                raise

            assert_pico_ok(self.status["changePowerSource"])

        # ----------
        # Setup Channels, Trigger, Time
        # ----------

        # ----- Set up channel A
        handle = self.chandle
        channel = PS4000_CHANNEL_A = 0
        enabled = 1
        coupling_type = PS4000_DC = 1
        self.chARange = 7
        self.status["setChA"] = ps.ps4000SetChannel(handle, channel, enabled, coupling_type, self.chARange)
        assert_pico_ok(self.status["setChA"])

        # ----- Set up channel B
        handle = self.chandle
        channel = PS4000_CHANNEL_B = 1
        enabled = 1
        coupling_type = PS4000_DC = 1
        self.chBRange = 7
        self.status["setChB"] = ps.ps4000SetChannel(handle, channel, enabled, coupling_type, self.chBRange)
        assert_pico_ok(self.status["setChB"])

        # ----- Set up simple Trigger
        handle = self.chandle
        enabled = 1
        # source = PS4000_CHANNEL_B
        source = self.trigger_chan_number
        threshold = mV2adc(self.trigger_threshold, self.chBRange, self.maxADC)
        direction = PS4000_RISING = 2
        delay = 0 # s
        autoTrigger_ms = 1 # ms  #TODO: Autotriggers after some time ?
        self.status["trigger"] = ps.ps4000SetSimpleTrigger(handle, enabled, source, threshold, direction, delay, autoTrigger_ms )
        assert_pico_ok(self.status["trigger"])

        # ----- Setup Timebase
        handle = self.chandle
        self.timebase = self.timebase
        noSamples = self.maxSamples
        self.timeIntervalns = ctypes.c_float()
        pointer_to_timeIntervalNanoseconds = ctypes.byref(self.timeIntervalns)
        returnedMaxSamples = ctypes.c_int32()
        pointer_to_maxSamples = ctypes.byref(returnedMaxSamples)
        segment_index = 0
        oversample = ctypes.c_int16(1)
        self.status["getTimebase2"] = ps.ps4000GetTimebase2(handle, self.timebase, noSamples, pointer_to_timeIntervalNanoseconds, oversample, pointer_to_maxSamples, segment_index)
        assert_pico_ok(self.status["getTimebase2"])

        # ----------
        # Setup Memory and Buffers
        # ----------

        # ----- Set  up memory segments
        handle = self.chandle
        nSegments = 10
        nMaxSamples = ctypes.c_int32(0)
        self.status["setMemorySegments"] = ps.ps4000MemorySegments(self.chandle, 10, ctypes.byref(nMaxSamples))
        assert_pico_ok(self.status["setMemorySegments"])

        # ----- Set number of captures
        handle = self.chandle
        nCaptures = 1
        self.status["SetNoOfCaptures"] = ps.ps4000SetNoOfCaptures(handle, nCaptures)
        assert_pico_ok(self.status["SetNoOfCaptures"])

        # ----- Create buffers
        self.bufferA = (ctypes.c_int16 * self.maxSamples)()
        self.bufferB = (ctypes.c_int16 * self.maxSamples)()

        # ----- Assign buffers
        handle = self.chandle
        channelA = PS4000_CHANNEL_A = 0
        channelB = PS4000_CHANNEL_B = 1
        bufferLength = self.maxSamples
        mode = PS4000_RATIO_MODE_NONE = 0

        self.status["setDataBufferA"] = ps.ps4000SetDataBuffer(handle, PS4000_CHANNEL_A, ctypes.byref(self.bufferA), bufferLength)
        self.status["setDataBufferB"] = ps.ps4000SetDataBuffer(handle, PS4000_CHANNEL_B, ctypes.byref(self.bufferB), bufferLength)



    ############## PMD mandatory methods

    def get_the_x_axis(self):
        print("Tut")
        return 0
        # return self.data_transfer.time_data().magnitude


    def start_a_grab_snap(self):

        # ----------
        # Get Data
        # ----------
        with self._lock:
            # ----- Run Block Capture
            # This will continue to run until buffer is full, then ps4000IsReady gives a "go"
            handle = self.chandle
            noOfPreTriggerSamples = self.preTriggerSamples
            noOfPostTriggerSamples = self.postTriggerSamples
            timebase = self.timebase
            timeIndisposedMs = None # not needed here
            segment_index = 0
            lpReady = None # using ps4000IsReady rather than ps4000BlockReady
            pParameter = None
            oversample = ctypes.c_int16(1)
            self.status["runBlock"] = ps.ps4000RunBlock(handle, noOfPreTriggerSamples, noOfPostTriggerSamples,  timebase, oversample, timeIndisposedMs, segment_index, lpReady, pParameter)
            assert_pico_ok(self.status["runBlock"])


            # --- Check for end of capture
            ready = ctypes.c_int16(0)
            check = ctypes.c_int16(0)
            while ready.value == check.value:
                self.status["isReady"] = ps.ps4000IsReady(self.chandle, ctypes.byref(ready))

            # Creates a overflow location for data
            overflow = (ctypes.c_int16 * 10)()
            # Creates converted types maxsamples
            cmaxSamples = ctypes.c_int32(self.maxSamples)


            # ---- Collect data from buffer
            handle = self.chandle
            start_index = 0
            pointer_to_number_of_samples = ctypes.byref(cmaxSamples)
            downsample_ratio = 0
            downsample_ratio_mode = PS4000_RATIO_MODE_NONE = 0
            segmentIndex = 0
            pointer_to_overflow = ctypes.byref(overflow)

            self.status["getValues"] = ps.ps4000GetValues(self.chandle, start_index, pointer_to_number_of_samples, downsample_ratio, downsample_ratio_mode, segmentIndex, pointer_to_overflow)
            assert_pico_ok(self.status["getValues"])

            # # convert from adc to mV
            channelA_data =  adc2mV(self.bufferA, self.chARange, self.maxADC)
            channelB_data =  adc2mV(self.bufferB, self.chBRange, self.maxADC)

            # Create time data
            time = np.linspace(0, ((cmaxSamples.value)-1) * self.timeIntervalns.value * 1e-9, cmaxSamples.value)

            return time, [np.array(channelA_data), np.array(channelB_data)]

    def set_timebase(self, aquire_time=None, sampling_freq=None):
        if aquire_time: self.num_points = self.sampling_frequency*1e6 *aquire_time
        elif sampling_freq: self.num_points = sampling_freq*1e6 *self.aquire_time

        self.postTriggerSamples = int( self.num_points - self.preTriggerSamples)
        self.maxSamples = int(self.preTriggerSamples + self.postTriggerSamples)

    def setup_sig_gen(self, wave_type=0, freq_hz=1000.0, pk2pk_uv=2_000_000, offset_uv=0):
        """Configure the ps4000 built-in signal generator."""
        with self._lock:
            print(f"\n[WRAPPER4000 setup_sig_gen] wave={wave_type}, freq={freq_hz}, "
                f"pk2pk_uv={pk2pk_uv}, offset_uv={offset_uv}")

            # ps4000SetSigGenBuiltIn signature:
            # (handle, offsetVoltage, pkToPk, waveType,
            #  startFrequency, stopFrequency, increment, dwellTime,
            #  sweepType, operationType, shots, sweeps,
            #  triggerType, triggerSource, extInThreshold)
            status = ps.ps4000SetSigGenBuiltIn(
                self.chandle,
                int(offset_uv),       # offsetVoltage (uV)
                int(pk2pk_uv),        # pkToPk (uV)
                int(wave_type),       # waveType
                float(freq_hz),       # startFrequency
                float(freq_hz),       # stopFrequency
                float(0),             # increment
                float(0),             # dwellTime
                int(0),               # sweepType (UP)
                int(0),               # operationType (normal)
                int(0),               # shots (continuous)
                int(0),               # sweeps (continuous)
                int(0),               # triggerType (rising)
                int(0),               # triggerSource (none)
                int(0)                # extInThreshold
            )
            print(f"[WRAPPER4000 setup_sig_gen] SDK status: {status}")
            assert_pico_ok(status)
            print(f"[WRAPPER4000 setup_sig_gen] Done")

    def stop_sig_gen(self):
        """Stop the signal generator."""
        with self._lock:
            ps.ps4000SetSigGenBuiltIn(
                self.chandle, 0, 0, 0,
                0.0, 0.0, 0.0, 0.0,
                0, 0, 0, 0, 0, 0, 0
            )


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
    
    


# pico = Picoscope_Wrapper()
# pico.start_a_grab_snap()
