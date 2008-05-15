#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Device Daemon - A plugin for the main object

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.5.0"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile
from gobject import idle_add
try:
    import wireless
except ImportError:
    wireless = None
    LOG( LOG_ERR, "wireless module not available" )

#----------------------------------------------------------------------------#
class Main( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """An D-Bus Object implementing org.freesmartphone.Device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX  

    def __init__( self, bus, controller ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        dbus.service.Object.__init__( self, bus, self.path )
        self.controller = controller

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "s", "ao" )
    def List( self, interface ):
        return [x for x in self.controller.objects.values() if x.interface == interface]

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [Main( controller.bus, controller )]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    def requestInterfaceForObject( prefix, interface, object ):
        proxy = bus.get_object( prefix, object )
        #print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
        iface = dbus.Interface(proxy, interface )
        return iface

    iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, Main.DBUS_INTERFACE, DBUS_PATH_PREFIX )
    print "org.freesmartphone.Device.Display", iface.List( "org.freesmartphone.Device.Display" )
    print "org.freesmartphone.Device.PowerSupply", iface.List( "org.freesmartphone.Device.PowerSupply" )

