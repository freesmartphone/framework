#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Event Daemon - Trigger objects

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Event.Trigger"
DBUS_PATH_PREFIX = "/org/freesmartphone/Event/Trigger"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

#----------------------------------------------------------------------------#
class Trigger( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """An abstract Dbus Object implementing
    org.freesmartphone.Trigger"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX
    INDEX = 0

    def __init__( self, controller ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/%s" % Trigger.INDEX
        Trigger.INDEX += 1
        self.controller = controller
        dbus.service.Object.__init__( self, controller.bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" %
            ( self.__class__.__name__, self.interface, list( self.locations ) )
        )

#----------------------------------------------------------------------------#
class DBusTrigger( Trigger ):
#----------------------------------------------------------------------------#
    def __init__( self, controller, signal_name, interface_name, bus_name, object_path, callback ):
        Trigger.__init__( self, controller )
        self.bus_name = bus_name
        self.interface_name = interface_name
        self.object_path = object_path
        self.signal_name = signal_name
        controller.bus.add_signal_receiver( callback, signal_name, interface_name, bus_name, object_path )

#----------------------------------------------------------------------------#
class CallTrigger( DBusTrigger ):
#----------------------------------------------------------------------------#
    def __init__( self, controller ):
        DBusTrigger.__init__(
            self, controller,
            'CallStatus',
            'org.freesmartphone.GSM.Call',
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/Device',
            self.handle)
        self.calls = {}

    def handle( self, id, status, properties ):
        from manager import Manager
        if not id in self.calls: # new call
            signal = Manager.instance.CreateSignal({'type': 'Call', 'status': status})
            self.calls[id] = signal
            self.calls[id].fire()
            print self.calls[id], 'fired', self.calls[id].attributes
        else: # updated call
            oldstatus = self.calls[id].attributes['status']
            self.calls[id].attributes['status'] = status
            self.calls[id].fire()
            print self.calls[id], 'fired', self.calls[id].attributes
        if status == "release":
            signal = self.calls[id]
            signal.release()
            del self.calls[id]
            print signal, 'deleted'
        
#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []
    objects.append( CallTrigger( controller ) )
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

