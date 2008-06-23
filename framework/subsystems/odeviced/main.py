#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Device Daemon - A plugin for the main object

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.5.1"

import os, sys
import dbus.service
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile

#----------------------------------------------------------------------------#
class Main( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A D-Bus Object implementing org.freesmartphone.Device"""
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
    def ListObjectsByInterface( self, interface ):
        if interface == "*":
            return [x for x in self.controller.objects.values()]
        elif interface.endswith( '*' ):
            return [x for x in self.controller.objects.values() if x.interface.startswith( interface[:-1] )]
        else:
            return [x for x in self.controller.objects.values() if x.interface == interface]

    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetCpuInfo( self ):
        cpuinfo = readFromFile( "/proc/cpuinfo" ).split( '\n' )
        d = {}
        for line in cpuinfo:
            try:
                key, value = line.split( ':' )
            except ValueError: # no valid line
                continue
            d[key.strip()] = value.strip()
        return d

    # FIXME Do we want statistics (GetMemInfo, GetUptime, GetLoadAverage...)

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

