#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Device Daemon - Objects Query Object

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

__version__ = "0.5.1"

import os, sys
import dbus.service
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

#----------------------------------------------------------------------------#
class Objects( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A D-Bus Object implementing org.freesmartphone.Objects"""
    DBUS_INTERFACE = "org.freesmartphone.Objects"

    def __init__( self, bus, controller ):
        self.interface = self.DBUS_INTERFACE
        self.path = "/org/freesmartphone/Framework"
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

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ Objects( controller.bus, controller ) ]

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    import dbus
    bus = dbus.SystemBus()

    query = bus.get_object( "org.freesmartphone.frameworkd", "/org/freesmartphone/Framework" )
    objects = query.ListObjectsByInterface( '*' )

    phone = bus.get_object( "org.freesmartphone.ophoned", "/org/freesmartphone/GSM/Device" )
