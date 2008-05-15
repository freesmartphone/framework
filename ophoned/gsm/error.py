#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from dbus import DBusException

#=========================================================================#
# Base exceptions
#=========================================================================#

class AbstractDeviceException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device"

class AbstractSimException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM"

class AbstractNetworkException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network"

class AbstractCallException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call"

class UnsupportedCommand( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.UnsupportedCommand"

class InternalException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.InternalError"

#=========================================================================#
# Device exceptions
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

class SimNotPresent( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.NotPresent"

class SimAuthFailed( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.AuthFailed"

class SimBlocked( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.Blocked"

class SimNotFound( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.NotFound"

class SimMemoryFull( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.MemoryFull"

#=========================================================================#
# Network exceptions
#=========================================================================#

class NetworkNotPresent( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.Network.NotPresent"

class NetworkUnauthorized( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.Network.Unauthorized"

class NetworkNotFound( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.Network.NotFound"

#=========================================================================#
# Call exceptions
#=========================================================================#

class CallNotFound( AbstractCallException ):
    _dbus_error_name = "org.freesmartphone.Call.NotFound"

