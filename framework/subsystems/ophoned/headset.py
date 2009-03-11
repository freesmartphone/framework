# -*- coding: UTF-8 -*-
"""
Open Phone Daemon - BlueZ headset interface

(C) 2009 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2009 Openmoko, Inc.
GPLv2 or later

Package: ophoned
Module: headset
"""

import dbus

class ConfigurationError( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Phone.ConfigurationError"

class HeadsetManager( object ):
    def __init__( self, bus ):
        self.bus = bus
        self.address = None
        self.enabled = False

    def setAddress( self, address ):
        self.address = address

    def setEnabled( self, enabled ):
        if not self.enabled and enabled:
            if not self.address:
                raise ConfigurationError("Address not set")
            # we expect bluetooth to be enabled already, should we request the resource here?
            bluez_manager_proxy = self.bus.get_object(
                "org.bluez",
                "/",
            )
            self.bluez_manager = dbus.Interface(
                bluez_manager_proxy,
                "org.bluez.Manager",
            )
            bluez_adapter_proxy = self.bus.get_object(
                "org.bluez",
                self.bluez_manager.DefaultAdapter(),
            )
            self.bluez_adapter = dbus.Interface(
                bluez_adapter_proxy,
                "org.bluez.Adapter",
            )
            bluez_device_proxy = self.bus.get_object(
                "org.bluez",
                self.bluez_adapter.FindDevice( self.address ),
            )
            self.bluez_device = dbus.Interface(
                bluez_device_proxy,
                "org.bluez.Adapter",
            )
            self.enabled = enabled
        elif self.enabled and not enabled:
            self.enabled = enabled

