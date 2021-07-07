#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  2 09:46:11 2021

@author: aurelien
"""
import microscope

try:
    import microscope._wrappers.thorlabs_motionControl as TMC
except Exception as e:
    raise microscope.LibraryLoadError(e) from e
    
import microscope
import microscope.abc

from ctypes import c_char_p, c_double, create_string_buffer

import time

class ThorlabsNanoMaxAxis(microscope.abc.StageAxis):
    def __init__(self, serial_number, axis):
        """Axis of stepper motor Thorlabs NanoMax stage
        Parameters:
            serial_number (c_char_p): the stage serial number
            axis (int): the index of the axis, starting from 1.
        """
        self.serial_number = serial_number
        self.axis = axis

    @property        
    def limits(self):
        mintravel = c_double(20)
        maxtravel = c_double(10)
        TMC.SBC_GetMotorTravelLimits(self.serial_number, self.axis, mintravel, 
                                 maxtravel)
        return microscope.AxisLimits(0, 5553600)
    
    def move_by(self, delta):
        status = TMC.SBC_MoveRelative(self.serial_number,self.axis,int(delta))
        if status:
            message = "Error"
            if status in TMC.errors_dict.keys():
                message = TMC.errors_dict[status]
            raise microscope.DeviceError(message)
        time.sleep(.8)
            
    def move_to(self, pos):
        # pos: int
        status = TMC.SBC_MoveToPosition(self.serial_number, self.axis, int(pos))
        if status:
            message = "Error"
            if status in TMC.errors_dict.keys():
                message = TMC.errors_dict[status]
            raise microscope.DeviceError(message)
        time.sleep(.8)
            
    @property
    def position(self):
        pos = TMC.SBC_GetPosition(self.serial_number, self.axis)
        return pos
    
class ThorlabsNanoMax(microscope.abc.Stage):
    """A Thorlabs Nanomax stage. So far supports only 3-axis, stepper-motor stage"""
    def __init__(self, serial_number: str, **kwargs) -> None:
        super().__init__(**kwargs)

        out = TMC.TLI_BuildDeviceList()
        if out != 0:
            raise RuntimeError('ups')
#        n = TMC.TLI_GetDeviceListSize()
#        serialNos = create_string_buffer(100)
#        TMC.TLI_GetDeviceListByTypeExt(serialNos, 100, 70)
    
        self.serial_number = c_char_p(bytes(serial_number, "utf-8"))
        status = TMC.SBC_Open(self.serial_number)

        if status:
            raise microscope.InitialiseError(status)
        # populate axes dict
        self.n_axes = 3 # can be updated later
        axes_names = ["x","y","z"]
        self._axes = {}
        for j in range(self.n_axes):
            time.sleep(5)
            status =TMC.SBC_LoadSettings(self.serial_number,j+1)
            print(status)
            axn = axes_names[j]
            self._axes[axn]=ThorlabsNanoMaxAxis(self.serial_number,j+1)

    def enable(self):
        # homing
        # !!! Might need to wait for homing to finish axis by axis
        for channel_nr in range(self.n_axes):
            status = TMC.SBC_Home(self.serial_number, channel_nr+1)
            if status:
                message = "Error"
                if status in TMC.errors_dict.keys():
                    message = TMC.errors_dict[status]
                raise microscope.DeviceError(message)
        time.sleep(15)
        
    
    def _do_shutdown(self):
        status = TMC.SBC_Close(self.serial_number)
        if status:
            message = "Error"
            if status in TMC.errors_dict.keys():
                message = TMC.errors_dict[status]
            raise microscope.DeviceError(message)
        
    @property
    def axes(self):
        return self._axes
        
    def move_by(self, delta):
        for ax, delta in self.axes.items():
            self.axes[ax].move_by(delta)
            
    def move_to(self, position):
        for ax, delta in self.axes.items():
            self.axes[ax].move_to(delta)