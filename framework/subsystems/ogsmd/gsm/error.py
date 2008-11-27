#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: error

DBus Exception Classes for org.freesmartphone.GSM*
"""

from dbus import DBusException

#=========================================================================#
# GSM exceptions, unspecific to actual interface
#=========================================================================#

class UnsupportedCommand( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.UnsupportedCommand"

class InvalidParameter( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.InvalidParameter"

class InternalException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.InternalError"

class NoCommandToCancelException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.NoCommandToCancel"

class CommandCancelled( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.CommandCancelled"

#=========================================================================#
# Base classes for interface-specific exceptions
#=========================================================================#

class AbstractDeviceException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Device"

class AbstractSimException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM"

class AbstractNetworkException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network"

class AbstractCallException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call"

class AbstractPdpException( DBusException ):
    _dbus_error_name = "org.freesmartphone.GSM.PDP"

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

class SimInvalidIndex( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.InvalidIndex"

class SimNotReady( AbstractSimException ):
    _dbus_error_name = "org.freesmartphone.GSM.SIM.NotReady"

#=========================================================================#
# Network exceptions
#=========================================================================#

class NetworkNotPresent( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network.NotPresent"

class NetworkUnauthorized( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network.Unauthorized"

class NetworkNotSupported( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network.NotSupported"

class NetworkNotFound( AbstractNetworkException ):
    _dbus_error_name = "org.freesmartphone.GSM.Network.NotFound"

#=========================================================================#
# Call exceptions
#=========================================================================#

class CallNoCarrier( AbstractCallException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call.NoCarrier"

class CallNotFound( AbstractCallException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call.NotFound"

class CallNotAnEmergencyNumber( AbstractCallException ):
    _dbus_error_name = "org.freesmartphone.GSM.Call.NotAnEmergencyNumber"

#=========================================================================#
# PDP exceptions
#=========================================================================#

class PdpNoCarrier( AbstractPdpException ):
    _dbus_error_name = "org.freesmartphone.GSM.PDP.NoCarrier"

class PdpNotFound( AbstractPdpException ):
    _dbus_error_name = "org.freesmartphone.GSM.PDP.NotFound"

class PdpUnauthrized( AbstractPdpException ):
    _dbus_error_name = "org.freesmartphone.GSM.PDP.Unauthorized"
