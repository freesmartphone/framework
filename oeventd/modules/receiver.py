#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Event Daemon - Receiver objects

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Event.Receiver"
DBUS_PATH_PREFIX = "/org/freesmartphone/Event/Receiver"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

#----------------------------------------------------------------------------#
class Receiver( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Event.Receiver"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX
    INDEX = 0

    def __init__( self, bus, action, filter = None ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        dbus.service.Object.__init__( self, bus, self.path + "/%s" % Receiver.INDEX )
        Receiver.INDEX += 1
        self.action = action
        self.filter = filter
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" %
            ( self.__class__.__name__, self.interface, list( self.locations ) )
        )

    def matchEvent( self, event ):
        return self.filter is None or self.filter( event )

    def handleEvent( self, event ):
        assert self.matchEvent( event)
        self.action( event )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []
    def printAction( event ):
        print event
    objects.append( Receiver( controller.bus, printAction ) )
    return objects

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    def requestInterfaceForObject( prefix, interface, object ):
        proxy = bus.get_object( prefix, object )
        #print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
        iface = dbus.Interface( proxy, interface )
        return iface

    usage = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, GenericUsageControl.DBUS_INTERFACE, DBUS_PATH_PREFIX )

    print "Found resources:", usage.ListResources()
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Requesting GSM..."
    usage.RequestResource("GSM")
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Releasing GSM..."
    usage.ReleaseResource("GSM")
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Disabling GSM..."
    usage.SetResourcePolicy("GSM", "disabled")
    print "Enabling GSM..."
    usage.SetResourcePolicy("GSM", "enabled")
    print "Setting GSM to auto..."
    usage.SetResourcePolicy("GSM", "auto")

