#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from dbus import DBusException

#=========================================================================#
# base exceptions
#=========================================================================#

class AbstractDeviceException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device"

class AbstractSimException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM"

class AbstractNetworkException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network"

class AbstractCallException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call"

#=========================================================================#
# device exceptions
#=========================================================================#

class DeviceTimeout( AbstractDeviceException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device.Timeout"

class DeviceNotPresent( AbstractDeviceException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device.NotPresent"

class DeviceFailed( AbstractDeviceException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device.Failed"

#=========================================================================#
# SIM exceptions
#=========================================================================#


#=========================================================================#
# network exceptions
#=========================================================================#


#=========================================================================#
# call exceptions
#=========================================================================#

