#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Event Daemon - Manager

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Event"
DBUS_PATH_PREFIX = "/org/freesmartphone/Event"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

import logging
logger = logging.getLogger('oeventd')

#----------------------------------------------------------------------------#
class Signal( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Event.Signal"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX
    INDEX = 0

    def __init__( self, controller, attributes ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/%s" % Signal.INDEX
        Signal.INDEX += 1
        self.controller = controller
        self.attributes = attributes
        dbus.service.Object.__init__( self, controller.bus, self.path )
        logger.info( "%s initialized. Serving %s at %s",
            self.__class__.__name__, self.interface, list( self.locations )
        )

    def fire( self ):
        from receiver import Receiver
        for x in self.controller.objects.values():
            if isinstance( x, Receiver ):
                x.handleEvent( self )
        
    def release( self ):
        from receiver import Receiver
        for x in self.controller.objects.values():
            if isinstance( x, Receiver ):
                x.releaseEvent( self )
        Manager.instance.signals.remove( self )
        
    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetAttributes( self ):
        return self.attributes

#----------------------------------------------------------------------------#
class Manager( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Event"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX
    instance = None

    def __init__( self, controller ):
        assert Manager.instance == None
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        dbus.service.Object.__init__( self, controller.bus, self.path )
        self.controller = controller
        self.signals = []
        logger.info( "%s initialized. Serving %s at %s",
            self.__class__.__name__, self.interface, list( self.locations )
        )
        Manager.instance = self

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "ao" )
    def ListTriggers( self ):
        from trigger import Trigger
        return [x for x in self.controller.objects.values() if isinstance( x, Trigger ) ]

    @dbus.service.method( DBUS_INTERFACE, "", "ao" )
    def ListReceivers( self ):
        from receiver import Receiver
        return [x for x in self.controller.objects.values() if isinstance( x, Receiver ) ]

    @dbus.service.method( DBUS_INTERFACE, "", "ao" )
    def ListSignals( self ):
        return self.signals

    @dbus.service.method( DBUS_INTERFACE, "a{sv}", "o" )
    def CreateSignal( self, attributes ):
        signal = Signal( self.controller, attributes )
        self.signals.append( signal )
        return signal

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "s" )
    def ResourceChanged( self, resourcename ):
        pass

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ Manager( controller ) ]

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

