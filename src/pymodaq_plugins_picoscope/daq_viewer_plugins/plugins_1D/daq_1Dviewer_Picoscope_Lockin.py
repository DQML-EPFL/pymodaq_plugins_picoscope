import numpy as np
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataFromPlugins, Axis, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.parameter import Parameter

from pymodaq_plugins_picoscope.hardware.Picoscope4000_wrapper import Picoscope_Wrapper as Picoscope_Wrapper4000
from pymodaq_plugins_picoscope.hardware.Picoscope4000a_wrapper import Picoscope_Wrapper as Picoscope_Wrapper4000a


class DAQ_1DViewer_Picoscope_Lockin(DAQ_Viewer_base):
    """ Instrument plugin class for a 1D viewer.
    
    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library.
    """

    params = comon_parameters+[
        {"title": "Picoscope Series Version",
         "name": "pico_type",
         "type": "itemselect",
         "value": dict(all_items=["Picoscope 4000", "Picoscope 4000a"], selected=["Picoscope 4000a"])
        } ,

        {'title':'Aquisition Parameters : Need to Reload Detector if changed !!',
         'name':'aquisition_param',
         'type':'group',
         'children':[        
             {'title':'Aquisition Time (ms)', 'name':'aquisition_time', 'type':'float', 'value':10, 'default':10 },
             {'title':'Sampling Frequency (MHz)', 'name':'sampling_freq', 'type':'float', 'value':0.2, 'default':0.2 },
             {'title':'Number of Samples (kS)', 'name':'num_samples', 'type':'float', 'value':2, 'default':2, 'readonly':True },
             {'title':'Trigger Channel', 'name':'trig_chan', 'type':'itemselect', 'value':dict(all_items=["A", "B", "External"], selected=["B"])},
             {'title':'Trigger Level (mV)', 'name':'trig_lvl', 'type':'float', 'value':500, 'default':500 } 
             ]},
        
        {'title':'Lock In Parameters',
         'name':'lockin_param',
         'type':'group',
         'children':[        
             {'title':'Remove Background ?', 'name':'rmv_bg', 'type':'bool_push', 'value':True, 'default':True },
             {'title':'B Frequency (Hz)', 'name':'B_freq', 'type':'float', 'value':500, 'default':500 },
             ]},
            
        {'title':'Display Parameters',
         'name':'display_param',
         'type':'group',
         'children':[
             {'title':'Lockin Display', 'name':'lockin_display', 'type':'group', 'children':[                   
                    {'title':'Raw Trace', 'name':'pulse_train', 'type':'led_push', 'value':False, 'default':False},
                    {'title': 'Integrated Pulse Train', 'name': 'pulse_train_int', 'type': 'led_push', 'value': False, 'default': False},
                    {'title': 'ND_Bd', 'name': 'ND_Bd', 'type': 'led_push', 'value': True, 'default': True},
            ]},

         ]},

        ]






    def ini_attributes(self):
        if self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000": self.controller: Picoscope_Wrapper4000 = None
        elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000a": self.controller: Picoscope_Wrapper4000a = None
        
        self.x_axis = None
        self.pico = None

        # Set all read only values
        self.settings.child('aquisition_param', 'num_samples').setValue( self.settings.child('aquisition_param', 'sampling_freq').value()*1e6 * self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3 * 1e-3 )
        self.x_axis = None
        self.pico = None

        # Set all read only values
        self.settings.child('aquisition_param', 'num_samples').setValue( self.settings.child('aquisition_param', 'sampling_freq').value()*1e6 * self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3 * 1e-3 )

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """

        print("Commit setting : ", param)
        if param.name() == "aquisition_time":   # TODO: Find a way to set Timebase while initialised
            sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value()
            aquire_time = param.value()
            num_points = (sampling_freq*1e6) * (aquire_time*1e-3) * 1e-3
            
            self.settings.child('aquisition_param', 'num_samples').setValue( num_points )

        if param.name() == "sampling_freq":   # TODO: Find a way to set Timebase while initialised
            # self.controller.set_timebase(sampling_freq=self.settings.child('aquisition_param', 'sampling_freq').value())
            sampling_freq = param.value()
            aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()
            num_points = (sampling_freq*1e6) * (aquire_time*1e-3) * 1e-3
            
            self.settings.child('aquisition_param', 'num_samples').setValue( num_points )

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one actuator/detector by controller
            (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """

        # Define Trigger Channel
        trigger_channel_number_dic = {"A":0, "B":1, "C":9}
        trigger_channel_number = trigger_channel_number_dic [self.settings.child('aquisition_param', 'trig_chan').value()['selected'][0] ]

        if (trigger_channel_number==9) and (self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000a"):
            print("ERROR : External channel not available for Picoscope 4000a")
        else:

            if self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000":
                print("Initialise 4000")
                self.controller = Picoscope_Wrapper4000( 
                                                    aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3,
                                                    sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value(),
                                                    trigger = self.settings.child('aquisition_param', 'trig_lvl').value(),
                                                    trigger_chan = trigger_channel_number
                                                    )  #
            elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000a": 
                print("Initialise 4000a")
                self.controller = Picoscope_Wrapper4000a( 
                                                    aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3,
                                                    sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value(),
                                                    trigger = self.settings.child('aquisition_param', 'trig_lvl').value(),
                                                    trigger_chan = trigger_channel_number
                                                    )  #instantiate you driver with whatever arguments are needed
            else: 
                print("Problem +")

            info = "Log info on Picoscope initialisation : Not coded Yet"
            initialized = True
        

        return info, initialized




    def close(self):
        """Terminate the communication protocol"""
        self.controller.__del__()


    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        ##synchrone version (blocking function)
        time, channels = self.controller.start_a_grab_snap()

        self.process_and_show_data(time, channels)



    def process_and_show_data(self, time, channels):
        
        ChannelA = channels[0]
        ChannelB = channels[1]

        # Parameters to set as Inputs for user
        B_frequency = self.settings.child('lockin_param', 'B_freq').value() * 1e-3      # kHz
        B_frequency *= 2 # We want to seperate by steps, not periods
        pulse_frequency = 1 # kHz
        
        sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value()
        aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()
        num_points = self.settings.child('aquisition_param', 'num_samples').value() * 1e3

        number_of_pulses = int(aquire_time * pulse_frequency)
        width_of_pulse = int(num_points / number_of_pulses)

        number_of_B = int(aquire_time * B_frequency)
        width_of_B = int(number_of_pulses/number_of_B)

        # Reshape Data (Seperate Pulses)
        ChannelA_reshaped = ChannelA.reshape(number_of_pulses, width_of_pulse)
        ChannelB_reshaped = ChannelB.reshape(number_of_pulses, width_of_pulse)

        # Calculate Pulses and remove background
        ChannelA_values = np.sum(ChannelA_reshaped[:,width_of_pulse//2:], axis=1) - np.sum(ChannelA_reshaped[:,:width_of_pulse//2], axis=1)
        ChannelB_values = np.sum(ChannelB_reshaped[:,width_of_pulse//2:], axis=1) - np.sum(ChannelB_reshaped[:,:width_of_pulse//2], axis=1)

        # Normalise Data
        ND = ChannelA_values / ChannelB_values
        
        # Reshape Data (Seperate Pulses)
        ND_reshaped = ND.reshape(number_of_B, width_of_B)

        # Compute ND_a
        ND_a = np.mean( ND_reshaped )

        # Compute ND_Bd
        if len(ND_reshaped)%2 !=0 : ND_reshaped = ND_reshaped[:-1]
        ND_Bd = np.mean( ND_reshaped[::2] - ND_reshaped[1::2] )
        
        # Plot a reference of the B
        Ref = np.ones( (number_of_B, int(width_of_B * width_of_pulse) ) ) * ChannelB.max()
        Ref[1::2] = 0; Ref = Ref.reshape(Ref.size,)


        # --- Plot the Data 
        data_to_export = []
        # 1D Data Plots
        
        if self.settings.child('display_param', 'lockin_display', 'pulse_train').value(): data_to_export.append( DataFromPlugins(name='Raw Trace', data=[ChannelA, ChannelB, Ref], dim='Data1D', labels=['Channel A', 'Channel B', "LockIn Reference"], do_plot=True, do_save=True) )
        if self.settings.child('display_param', 'lockin_display', 'pulse_train_int').value(): data_to_export.append( DataFromPlugins(name='Integrated and Background Removed', data=[ ChannelA_values, ChannelB_values ], dim='Data1D', labels=['Channel A', 'Channel B'], do_plot=True) )
        # DataPlot_Integrated = DataFromPlugins(name='Integrated and Background Removed', data=[ ChannelA_values, ChannelB_values ], dim='Data1D', labels=['Channel A', 'Channel B'], do_plot=True)


        # 0D Data Plots
        if self.settings.child('display_param', 'lockin_display', 'ND_Bd').value(): data_to_export.append( DataFromPlugins(name='ND_Bd', data= ND_Bd,  dim='Data0D', labels=['ND_Bd'], do_plot=True) )
        

        # --- Export the Data
        data = DataToExport('Picoscope', data=data_to_export)
        

        self.dte_signal.emit(data)





    def callback(self):
        """optional asynchrone method called when the detector has finished its acquisition of data"""
        data_tot = self.controller.your_method_to_get_data_from_buffer()
        self.dte_signal.emit(DataToExport('myplugin',
                                          data=[DataFromPlugins(name='Mock1', data=data_tot,
                                                                dim='Data1D', labels=['dat0', 'data1'])]))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        ## TODO for your custom plugin
        raise NotImplemented  # when writing your own plugin remove this line
        self.controller.your_method_to_stop_acquisition()  # when writing your own plugin replace this line
        self.emit_status(ThreadCommand('Update_Status', ['Some info you want to log']))
        ##############################
        return ''




if __name__ == '__main__':
    main(__file__, init=False)
