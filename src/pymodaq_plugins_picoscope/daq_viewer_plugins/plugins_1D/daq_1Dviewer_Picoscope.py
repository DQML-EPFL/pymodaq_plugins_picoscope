import numpy as np
from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataFromPlugins, Axis, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.parameter import Parameter

from pymodaq_plugins_picoscope.hardware.Picoscope4000_wrapper import Picoscope_Wrapper as Picoscope_Wrapper4000
from pymodaq_plugins_picoscope.hardware.Picoscope4000a_wrapper import Picoscope_Wrapper as Picoscope_Wrapper4000a
from pymodaq_plugins_picoscope.hardware.Picoscope2000_wrapper import Picoscope_Wrapper as Picoscope_Wrapper2000


class DAQ_1DViewer_Picoscope(DAQ_Viewer_base):
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
         "value": dict(all_items=["Picoscope 2000", "Picoscope 4000", "Picoscope 4000a"], selected=["Picoscope 2000"])
        } ,

        {'title':'Aquisition Parameters : Need to Reload Detector if changed !!',
         'name':'aquisition_param',
         'type':'group',
         'children':[        
             {'title':'Aquisition Time (ms)', 'name':'aquisition_time', 'type':'float', 'value':10, 'default':10 },
             {'title':'Sampling Frequency (MHz)', 'name':'sampling_freq', 'type':'float', 'value':0.2, 'default':0.2 },
             {'title':'Number of Samples (kS)', 'name':'num_samples', 'type':'float', 'value':2, 'default':2, 'readonly':True },
             {'title':'Trigger Channel', 'name':'trig_chan', 'type':'itemselect', 'value':dict(all_items=["A", "B", "External"], selected=["B"])},
             {'title':'Trigger Level (mV)', 'name':'trig_lvl', 'type':'float', 'value':100, 'default':500 },
             {'title':'Voltage Range','name':'voltage_range','type':'list','limits': {'±50 mV': 2,'±100 mV': 3,'±200 mV': 4,'±500 mV': 5,'±1 V': 6,'±2 V': 7,'±5 V': 8,'±10 V': 9}, 'value': 5,'default': 5} ]
        } ,

        ]


    # ----- Initialise 

    def ini_attributes(self):

        if self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000": self.controller: Picoscope_Wrapper4000 = None
        elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000a": self.controller: Picoscope_Wrapper4000a = None
        elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 2000": self.controller: Picoscope_Wrapper2000 = None
        
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
                                                    )  # TODO : implement voltage range
            elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 4000a": 
                print("Initialise 4000a")
                self.controller = Picoscope_Wrapper4000a( 
                                                    aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3,
                                                    sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value(),
                                                    trigger = self.settings.child('aquisition_param', 'trig_lvl').value(),
                                                    trigger_chan = trigger_channel_number
                                                    )  # TODO : implement voltage range
            elif self.settings.child('pico_type').value()["selected"][0] == "Picoscope 2000": 
                print("Initialise 2000")
                self.controller = Picoscope_Wrapper2000( 
                                                    aquire_time = self.settings.child('aquisition_param', 'aquisition_time').value()*1e-3,
                                                    sampling_freq = self.settings.child('aquisition_param', 'sampling_freq').value(),
                                                    trigger = self.settings.child('aquisition_param', 'trig_lvl').value(),
                                                    trigger_chan = trigger_channel_number,
                                                    voltage_range = self.settings.child('aquisition_param', 'voltage_range').value(), 
                                                    )  # TODO : implement pre_trig
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
        time, channels = self.controller.start_a_grab_snap()

        ChannelA = channels[0]/1000 # Convert to Volts
        ChannelB = channels[1]/1000 # Convert to Volts

        self.x_axis = Axis(data=time, label='Time', units="s", index=0) #self.controller.get_the_x_axis()

        dwa1D = DataFromPlugins(name='Channel B', data=[ChannelA, ChannelB], dim='Data1D', labels=['Channel A', 'Channel B'], do_plot=True, axes=[self.x_axis])

        data = DataToExport('Picoscope', data=[ dwa1D ])

        self.dte_signal.emit(data)




    




    def callback(self):
        """optional asynchrone method called when the detector has finished its acquisition of data"""
        data_tot = self.controller.your_method_to_get_data_from_buffer()
        self.dte_signal.emit(DataToExport('myplugin',
                                          data=[DataFromPlugins(name='Mock1', data=data_tot,
                                                                dim='Data1D', labels=['dat0', 'data1'])]))
    def stop(self):
        return ''   # PyMoDAQ expects a string return value from stop()




if __name__ == '__main__':
    main(__file__)
