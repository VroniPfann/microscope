#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 11:17:47 2022

@author: vpfannenstill
"""
## Copyright (C) 2021 David Miguel Susano Pinto <carandraug@gmail.com>
##
## This file is part of Microscope.
##
## Microscope is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## Microscope is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Microscope.  If not, see <http://www.gnu.org/licenses/>.

import logging
import typing

import serial

import microscope
import microscope._utils
import microscope.abc


_LOGGER = logging.getLogger(__name__)

def _parse_bool(answer:bytes) -> bool:
    assert answer==b"0" or answer==b"1"
    return answer==b"1"

    


class _VersaLaseConnection:
    """Connection to the Stradus VersaLase.

    This is a simple wrapper to the Stradus VersaLase interface.  It only
    supports the parameter commands which reply with a single line
    which is all we need to support this on Python-Microscope.

    """

    def __init__(self, shared_serial: microscope._utils.SharedSerial) -> None:
        self._serial = shared_serial

        self._serial.readlines()  # discard anything that may be on the line
       
        with self._serial.lock:
            self._serial.write(b'?SPV\r')
            empty_line = self._serial.readline()
            if empty_line != b'\r\n':
                raise microscope.DeviceError("not a Vortran Laser device")
            answer = self._serial.readline()
            if not answer.startswith(b'?SPV='):
                raise microscope.DeviceError("not a Vortran VersaLase device")
        self._command(b'ECHO=0')
        self._command(b'PROMPT=0')
        self._serial.readlines()  #discarding replies from ECHO and PROMPT commands

    def _command(self, command: bytes) -> bytes:
        """Run command and return raw answer (minus prompt and echo)."""
        command = command
        with self._serial.lock:
            self._serial.write(command + b"\r")
            empty_line=self._serial.readline()
            answer = self._serial.read_until(b"\r\n")

        # some replies end with b'\r\r\n' and some with b'\r\n' 
        if answer == b'\r\n' or answer == b'':
            raise microscope.DeviceError(
                "Failed to set command %s"
                % (answer)
            )
        else:
            #assert answer[: len(command)] == command
            if answer[-3:] == b'\r\r\n':
                if answer[len(command)+1:-3] == b'':
                    return answer[:len(command)]
                else:
                    return answer[len(command)+1: -3]
            else:
                assert answer[-2:] == b'\r\n'
                if answer[len(command)+1:-2] == b'':
                    return answer[:len(command)]
                else:
                    return answer[len(command)+1: -2]

    def query(self, name: bytes) -> bytes:
        """Get parameter value (? operator)."""
        return self._command(b"?%s" % name)

    def param_command(self, name: bytes, value: bytes) -> None:
        """Change parameter."""
        answer = self._command(b"%s=%s" % (name, value))
        #status = int(answer)
        
        #if status < 0:
            #raise microscope.DeviceError(
                #"Failed to set parameter %s (return value %d)"
                #% (name.decode(), status)
            #)


    def base_plate_temperature(self) -> int:            #0-55 degrees
        return int(self.query(b"BPT"))

    def interlock_status(self) -> bool:                     # 1=closed, 0=open
        return _parse_bool(self.query(b"IL"))

    def show_firmware_version(self) -> str:                 
        return self.query(b"SFV").decode()

    def show_protocol_version(self) -> str:                 
        return self.query(b"SPV").decode()



class _VersaLaseLaserConnection:
    def __init__(self, conn: _VersaLaseConnection, laser_number: int) -> None:
        self._conn = conn
        self._param_prefix = b"%d." % laser_number

        # We Need to confirm that indeed there is a laser at this
        # position.  There is no command to check this, we just try to
        # read a parameter and check if it works.
        try:
            self.get_wavelength()
            self.set_delay(0)
        except microscope.DeviceError as ex:
            raise microscope.DeviceError(
                "failed to get laser wavelength, probably no laser %d" % laser_number
            ) from ex

    def _laser_query(self, name: bytes) -> bytes:
        return self._conn._command(self._param_prefix + b"?%s" % name) #queries need to look as e.g. 2.?le

    def _laser_command(self, name: bytes, value: bytes) -> None:    #commands look like e.g. 2.le=1
        self._conn.param_command(self._param_prefix + name, value)

    def set_drive_control_mode(self, state:bool) -> None:         #if C=1 current control mode 
        value = b"1" if state else b"0"
        self._laser_command(b"C", value)

    def set_delay(self, state:bool) -> None:          
        value = b"1" if state else b"0"
        self._laser_command(b"DELAY", value)

    def set_external_power_control(self, state:bool) -> None:      #if EPC=1 means external control    
        value = b"1" if state else b"0"
        self._laser_command(b"EPC", value)

    def set_emission(self, state:bool) -> None:         
        value = b"1" if state else b"0"
        self._laser_command(b"LE", value)

    def set_power(self, power:float) -> None:      #range 0 to Max laser power system is calibrated to     
        value = b"%.1f" %power
        self._laser_command(b"LP", value)

    def set_pulse_power(self, pulsepower:float) -> None:      #range 0 to Max laser power system is calibrated to, only when C=0     
        value = b"%.1f" %pulsepower
        self._laser_command(b"PP", value)
        
    def set_pulse_mode(self, state:bool) -> None:      # Digital Modulation PUL=1     
        value = b"1" if state else b"0"
        self._laser_command(b"PUL", value)

    def get_drive_control_mode(self) -> bool:
        return _parse_bool(self._laser_query(b"C"))

    def get_computer_control(self) -> bool:             # 1=AUTOSTART, 0=MANUAL START
        return _parse_bool(self._laser_query(b"CC"))

    def get_delay(self) -> bool:
        return _parse_bool(self._laser_query(b"DELAY"))

    def get_emission_status(self) -> bool:
        return _parse_bool(self._laser_query(b"LE"))

    def get_operating_hours(self) -> int:             
        return int(self._laser_query(b"LH"))

    def get_identification(self) -> str:             #returns list of Unique Information (S/N, Part Number, Nom. λ, Nom. Power, C/E for circular or elliptical)
        return self._laser_query(b"LI").decode()

    def get_power(self) -> float:             
        return float(self._laser_query(b"LP"))

    def get_power_setting(self) -> float:             
        return float(self._laser_query(b"LPS"))

    def get_wavelength(self) -> int:             
        return int(self._laser_query(b"LW"))

    def get_max_power(self) -> float:             
        return float(self._laser_query(b"MAXP"))

    def get_pulse_power(self) -> int:             
        return int(self._laser_query(b"PP"))

    def get_pulse_mode(self) -> bool:
        return _parse_bool(self._laser_query(b"PUL"))

    def get_external_power_control_mode(self) -> bool:
        return _parse_bool(self._laser_query(b"EPC"))
    


class _VersaLaseLaser(microscope.abc.LightSource):
    def __init__(self, conn: _VersaLaseConnection, laser_number: int) -> None:
        super().__init__()
        self._conn = _VersaLaseLaserConnection(conn, laser_number)
        self._max_power = float(self._conn.get_max_power())
        self._save_power = float(self._conn.get_power_setting())
        self._track_digital_modulation = bool(self._conn.get_pulse_mode())

        # FIXME: set values to '0' because we need to pass an int as
        # values for settings of type str.  Probably a bug on
        # Device.set_setting.
        self.add_setting("label", "int", self._conn.get_wavelength, None, values=tuple())
        self.add_setting("delay", "int", self._conn.get_delay, None, values=tuple())

    def get_status(self) -> typing.List[str]:
        return self._conn.get_identification().split()

    def get_is_on(self) -> bool:
        return self._conn.get_emission_status()

    def _do_get_power(self) -> float:
        return self._conn.get_power() / self._max_power

    def _do_set_power(self, power: float) -> None:
        if self._conn.get_emission_status() == True:            #changing power is only possible when laser is enabled
            self._conn.set_power(power * self._max_power)
        else:
            self._save_power = (power * self._max_power)
            raise microscope.DeviceError(
                "Failed to set power, laser is not enabled. But power setting has been saved"
            )

    #def _do_set_power(self, power: float) -> None:              #change power with EPC hack
     #  self._conn.set_external_power_control(True)
     #   self._conn.set_emission(True)
     #   self._conn.set_power(power * self._max_power)
     #   self._conn.set_emission(False)
      #  self._conn.set_external_power_control(False)
        

    def _do_enable(self) -> None:
        self._conn.set_emission(True)                           #changing power and digital modulation is only possible when laser is enabled
        if self._conn.get_power_setting() != self._save_power:
            self._conn.set_power(self._save_power)
        elif self._conn.get_pulse_mode() != self._track_digital_modulation:                                                                          
            self._conn.set_pulse_mode(self._track_digital_modulation)
        else:
            pass

    def _do_disable(self) -> None:
        self._conn.set_emission(False)

    def _do_shutdown(self) -> None:
        pass  # Nothing to do

    @property
    def trigger_mode(self) -> microscope.TriggerMode:
        return microscope.TriggerMode.BULB

    @property
    def trigger_type(self) -> microscope.TriggerType:
        if self._conn.get_pulse_mode():
            return microscope.TriggerType.HIGH
        else:
            return microscope.TriggerType.SOFTWARE

    def set_trigger(
        self, ttype: microscope.TriggerType, tmode: microscope.TriggerMode
    ) -> None:
        if tmode is not microscope.TriggerMode.BULB:
            raise microscope.UnsupportedFeatureError(
                "only importriggerMode.BULB mode is supported"
            )

        if ttype is microscope.TriggerType.HIGH:                #changing digital modulation is only possible when laser is enabled
            if self._conn.get_emission_status() == True:
                self._conn.set_pulse_mode(True)
            else:
                self._track_digital_modulation = True
                raise microscope.DeviceError(
                    "Failed to change to DM, but setting has been saved and will be changed once laser is enabled"
            )        
    
        elif ttype is microscope.TriggerType.SOFTWARE:
            if self._conn.get_emission_status() == True:
                self._conn.set_pulse_mode(False)
            else:
                self._track_digital_modulation = not True
                raise microscope.DeviceError(
                    "Failed to change to DM, but setting has been saved and will be changed once laser is enabled"
            )        
        else:
            raise microscope.UnsupportedFeatureError(
                "only trigger type HIGH and SOFTWARE are supported"
            )

    def _do_trigger(self) -> None:
        raise microscope.IncompatibleStateError(
            "trigger does not make sense in trigger mode bulb, only enable"
        )


class StradusVersaLase(microscope.abc.Controller):
    """Vortran Stradus VersaLase 8.

    The names of the light devices are `1`, `2`, `3`, ...

    """

    def __init__(self, port: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._lasers: typing.Dict[str, _VersaLaseLaser] = {}

        # Setting specified on the manual (VersaLase 8 User Manual B3)
        serial_conn = serial.Serial(
            port=port,
            baudrate=19200,
            timeout=6,  #longer timeout set as otherwise unreliable returns
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        shared_serial = microscope._utils.SharedSerial(serial_conn)
        versaLase_connection = _VersaLaseConnection(shared_serial)

        _LOGGER.info("Connected to VersaLase with protocol version (%s) and firmware version (%s)",
                     versaLase_connection.show_protocol_version(),
                     versaLase_connection.show_firmware_version()
            )

        # According to the manual the VersaLase 8 can have up to 8
        # lasers.  There doesn't seem to be a simple command to check
        # what's installed, we'd have to parse the whole summary
        # table.  So we try/except to each laser line.
        for i in range(1, 9):
            name = "laser%d" % i
            try:
                laser = _VersaLaseLaser(versaLase_connection, i)
            except microscope.DeviceError:
                _LOGGER.info("no %s available", name)
                continue
            else:
                _LOGGER.info("found %s on VersaLase 8", name)
                self._lasers[name] = laser

    @property
    def devices(self) -> typing.Dict[str, _VersaLaseLaser]:
        return self._lasers
