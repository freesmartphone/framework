#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic usage support

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

class AbstractResource( object ):
    def __init__( self, usageControl ):
        self.usageControl = usageControl
        self.name = "Abstract"
        self.users = []

    def _enable( self ):
        pass

    def _disable( self ):
        pass

    def request( self, user ):
        assert user not in self.users, "User %s already requested %s" % ( user, self.name )
        self.users.append( user )
        if len( self.users ) == 1:
            self._enable()
            self.usageControl.ResourceChanged( self.name, True )

    def release( self, user ):
        assert user in self.users, "User %s did non request %s before releasing it" % ( user, self.name )
        self.users.remove( user )
        if len( self.users ) == 0:
            self._disable()
            self.usageControl.ResourceChanged( self.name, False )

    def cleanup( self, user ):
        if user in self.users:
            self.release( user )
            LOG( LOG_INFO, "Releasing %s for vanished user %s" % ( self.name, user ) )

class DummyResource( AbstractResource ):
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl )
        self.name = name

    def _enable( self ):
        print "Enabled %s" % self.name

    def _disable( self ):
        print "Disabled %s" % self.name

#----------------------------------------------------------------------------#
class GenericUsageControl( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """An abstract Dbus Object implementing
    org.freesmartphone.Usage"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX

    def __init__( self, bus ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        dbus.service.Object.__init__( self, bus, self.path )
        self.resources = {}
        bus.add_signal_receiver(
            self.nameOwnerChangedHandler,
            "NameOwnerChanged",
            dbus.BUS_DAEMON_IFACE,
            dbus.BUS_DAEMON_NAME,
            dbus.BUS_DAEMON_PATH
        )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    def addResource( self, resource ):
        # FIXME check for existing resource with the same name
        self.resources[resource.name] = resource

    def nameOwnerChangedHandler( self, name, old_owner, new_owner ):
        if old_owner and not new_owner:
            for resource in self.resources.values():
                resource.cleanup( old_owner )
                
    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "as" )
    def ListResources( self ):
        return self.resources.keys()

    @dbus.service.method( DBUS_INTERFACE, "s", "as" )
    def GetResourceUsers( self, resourcename ):
        return self.resources[resourcename].users

    @dbus.service.method( DBUS_INTERFACE, "s", "b", sender_keyword='sender' )
    def RequestResource( self, resourcename, sender ):
        self.resources[resourcename].request( sender )
        return True

    @dbus.service.method( DBUS_INTERFACE, "s", "", sender_keyword='sender' )
    def ReleaseResource( self, resourcename, sender ):
        self.resources[resourcename].release( sender )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sb" )
    def ResourceChanged( self, resourcename, status ):
        LOG( LOG_INFO, "%s has been %s" % (resourcename, "enabled" if status else "disabled" ) )

#----------------------------------------------------------------------------#
def factory( prefix, bus, config ):
#----------------------------------------------------------------------------#
    objects = []
    genericUsageControl = GenericUsageControl( bus )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "GSM" ) )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "GPS" ) )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "Bluetooth" ) )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "WiFi" ) )
    objects.append( genericUsageControl )
    return objects

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
