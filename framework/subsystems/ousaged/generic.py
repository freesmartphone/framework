#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic usage support

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ousaged
Module: generic
"""

# XXX: We need to modify this module to use the new resource system

MODULE_NAME = "ousaged"
__version__ = "0.1.1"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

from helpers import readFromFile, writeToFile

import dbus
import dbus.service

from gobject import idle_add

import os, sys
import sys

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class AbstractResource( object ):
#----------------------------------------------------------------------------#
    """Base class for all resources
    
    This is the internal class used by the resource manager to keep track of a resource.
    Every resource has a name, a list of current users, and a policy.
    
    The policy can be 'auto', 'disabled' or 'enabled'
    """
    def __init__( self, usageControl, name = "Abstract" ):
        self.usageControl = usageControl
        self.name = name
        self.users = []
        self.policy = 'auto'
        self.isEnabled = False

    def _enable( self ):
        pass

    def _disable( self ):
        pass

    def _update( self ):
        if not self.isEnabled and (self.users or self.policy == 'enabled'):
            logger.info( "Enabling %s", self.name )
            self._enable()
            self.isEnabled = True
        elif self.isEnabled and not (self.users or self.policy == 'enabled'):
            logger.info( "Disabling %s", self.name )
            self._disable()
            self.isEnabled = False

    def setPolicy( self, policy ):
        assert policy in ['disabled', 'auto', 'enabled'], "Unknown policy %s" % ( policy )
        if self.users:
            assert policy in ['auto', 'enabled'], "Can't change to policy %s for %s" % ( policy, self.name )
        if self.policy != policy:
            self.policy = policy
            self._update()
            self.usageControl.ResourceChanged(
                self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
            )

    def request( self, user ):
        assert self.policy in ['auto', 'enabled'], "Request for %s is not allowed" % ( self.name )
        assert user not in self.users, "User %s already requested %s" % ( user, self.name )
        self.users.append( user )
        self._update()
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )

    def release( self, user ):
        assert user in self.users, "User %s did non request %s before releasing it" % ( user, self.name )
        self.users.remove( user )
        self._update()
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )

    def cleanup( self, user ):
        if user in self.users:
            self.release( user )
            logger.info( "Releasing %s for vanished user %s", self.name, user )

#----------------------------------------------------------------------------#
class DummyResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )

    def _enable( self ):
        print "Enabled %s" % self.name

    def _disable( self ):
        print "Disabled %s" % self.name

#----------------------------------------------------------------------------#
class ODeviceDResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )
        self.bus = dbus.SystemBus()

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

#----------------------------------------------------------------------------#
class OGPSDResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )
        self.bus = dbus.SystemBus()

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
class ClientResource( AbstractResource ):
#----------------------------------------------------------------------------#
    """A resource that is controled by an external client.
    
    The client needs to expose a dbus object implementing org.freesmartphone.Resource.
    It can register using the RegisterResource of /org/freesmartphone/Usage.
    If the client is written in python, it can use the framework.Resource class.
    """
    def __init__(self, usageControl, name, path, sender):
        """Create a new ClientResource
        
        Only the resource manager should call this method
        """
        super(ClientResource, self).__init__(usageControl, name)
        bus = dbus.SystemBus()
        self.obj = bus.get_object(sender, path)
        
    def _enable( self ):
        """Simply call the client Enable method"""
        def on_reply():
            pass
        def on_error(err):
            logger.error("Error while enabling resource : %s", err)
        self.obj.Enable(reply_handler=on_reply, error_handler=on_error)

    def _disable( self ):
        """Simply call the client Disable method"""
        def on_reply():
            pass
        def on_error(err):
            logger.error("Error while disabling resource : %s", err)
        self.obj.Disable(reply_handler=on_reply, error_handler=on_error)
        
    

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
        
    @dbus.service.method( DBUS_INTERFACE, "so", "", sender_keyword='sender' )
    def RegisterResource( self, resourcename, path, sender ):
        """Register a new resource from a client
        
        The client must provide a name for the resource, and a dbus object
        path to an object implementing org.freesmartphone.Resource interface
        """
        logger.info( "Register new resource %s", resourcename )
        resource = ClientResource( self, resourcename, path, sender )
        self.addResource( resource )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sba{sv}" )
    def ResourceChanged( self, resourcename, state, attributes ):
        pass
        

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []
    # FIXME remove hardcoding resources here and rather rely on presence of PowerControl interface
    # Problem: presence of these objects is then depending other subsystems, so need to
    # postpone this until we have subsystem dependency support in the controller
    genericUsageControl = GenericUsageControl( controller.bus )
#    genericUsageControl.addResource( DummyResource( genericUsageControl, "GSM" ) )
    genericUsageControl.addResource( OGPSDResource( genericUsageControl, "GPS" ) )
    genericUsageControl.addResource( ODeviceDResource( genericUsageControl, "Bluetooth" ) )
    genericUsageControl.addResource( ODeviceDResource( genericUsageControl, "WiFi" ) )
    genericUsageControl.addResource( ODeviceDResource( genericUsageControl, "UsbHost" ) )
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

