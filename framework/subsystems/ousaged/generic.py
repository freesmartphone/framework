#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic usage support

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

import dbus
import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

import logging
logger = logging.getLogger('ousaged')

class AbstractResource( object ):
    def __init__( self, usageControl ):
        self.usageControl = usageControl
        self.name = "Abstract"
        self.users = []
        self.policy = 'auto'
        self.isEnabled = False

    def _enable( self ):
        pass

    def _disable( self ):
        pass

    def _update( self ):
        if not self.isEnabled and (self.users or self.policy == 'enabled'):
            self._enable()
            self.isEnabled = True
        elif self.isEnabled and not (self.users or self.policy == 'enabled'):
            self._disable()
            self.isEnabled = False

    def setPolicy( self, policy ):
        assert policy in ['disabled', 'auto', 'enabled'], "Unknown policy %s" % ( policy )
        if self.users:
            assert policy in ['auto', 'enabled'], "Can't change to policy %s for %s" % ( policy, self.name )
        if self.policy != policy:
            self.policy = policy
            self.usageControl.ResourceChanged( self.name )
            self._update()

    def request( self, user ):
        assert self.policy in ['auto', 'enabled'], "Request for %s is not allowed" % ( self.name )
        assert user not in self.users, "User %s already requested %s" % ( user, self.name )
        self.users.append( user )
        self.usageControl.ResourceChanged( self.name )
        self._update()

    def release( self, user ):
        assert user in self.users, "User %s did non request %s before releasing it" % ( user, self.name )
        self.users.remove( user )
        self.usageControl.ResourceChanged( self.name )
        self._update()

    def cleanup( self, user ):
        if user in self.users:
            self.release( user )
            logger.info( "Releasing %s for vanished user %s", self.name, user )

class DummyResource( AbstractResource ):
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl )
        self.name = name

    def _enable( self ):
        print "Enabled %s" % self.name

    def _disable( self ):
        print "Disabled %s" % self.name

class ODeviceDResource( AbstractResource ):
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl )
        self.bus = dbus.SystemBus()
        self.name = name

    def _replyCallback( self ):
        pass

    def _errorCallback( self, e ):
        pass

    def _enable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/PowerControl/" + self.name )
        iface = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        iface.SetPower( True, reply_handler=self._replyCallback, error_handler=self._errorCallback )
        print "Enabled %s" % self.name

    def _disable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/PowerControl/" + self.name )
        iface = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        iface.SetPower( False, reply_handler=self._replyCallback, error_handler=self._errorCallback )
        print "Disabled %s" % self.name

class OGPSDResource( AbstractResource ):
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl )
        self.bus = dbus.SystemBus()
        self.name = name

    def _replyCallback( self ):
        pass

    def _errorCallback( self, e ):
        pass

    def _enable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.ogpsd", "/org/freedesktop/Gypsy" )
        iface = dbus.Interface( proxy, "org.freesmartphone.GPS" )
        iface.SetPower( True, reply_handler=self._replyCallback, error_handler=self._errorCallback )
        print "Enabled %s" % self.name

    def _disable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.ogpsd", "/org/freedesktop/Gypsy" )
        iface = dbus.Interface( proxy, "org.freesmartphone.GPS" )
        iface.SetPower( False, reply_handler=self._replyCallback, error_handler=self._errorCallback )
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
        logger.info( "%s initialized. Serving %s at %s", self.__class__.__name__, self.interface, self.path )

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

    @dbus.service.method( DBUS_INTERFACE, "s", "b" )
    def GetResourceState( self, resourcename ):
        return self.resources[resourcename].isEnabled

    @dbus.service.method( DBUS_INTERFACE, "s", "s" )
    def GetResourcePolicy( self, resourcename ):
        return self.resources[resourcename].policy

    @dbus.service.method( DBUS_INTERFACE, "ss", "" )
    def SetResourcePolicy( self, resourcename, policy ):
        self.resources[resourcename].setPolicy( policy )

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
    @dbus.service.signal( DBUS_INTERFACE, "s" )
    def ResourceChanged( self, resourcename ):
        pass

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []
    genericUsageControl = GenericUsageControl( controller.bus )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "GSM" ) )
    genericUsageControl.addResource( OGPSDResource( genericUsageControl, "GPS" ) )
    genericUsageControl.addResource( ODeviceDResource( genericUsageControl, "Bluetooth" ) )
    genericUsageControl.addResource( DummyResource( genericUsageControl, "WiFi" ) )
    objects.append( genericUsageControl )
    return objects

if __name__ == "__main__":
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

