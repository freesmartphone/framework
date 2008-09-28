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

import framework.patterns.tasklet as tasklet

import dbus
import dbus.service

from gobject import idle_add

import os, sys, time

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
        """Create a new resource

        `usageControl` : the resource controler object that will handle this resource
        `name` : the name of the resource
        """
        self.usageControl = usageControl
        self.name = str(name)
        self.users = []
        self.policy = 'auto'
        self.isEnabled = False
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )

    @tasklet.tasklet
    def _enable( self ):
        """Enable the resource"""
        yield None

    @tasklet.tasklet
    def _disable( self ):
        """Disable the resource"""
        yield None

    @tasklet.tasklet
    def _suspend( self ):
        """Called before the system is going to suspend"""
        yield None

    @tasklet.tasklet
    def _resume( self ):
        """Called after a system resume"""
        yield None

    @tasklet.tasklet
    def _update( self ):
        if not self.isEnabled and (self.users or self.policy == 'enabled'):
            logger.debug( "Enabling %s", self.name )
            ts = time.time()
            yield self._enable()
            logger.info( "Enabled %s in %.1f seconds", self.name, time.time()-ts )
            self.isEnabled = True
        elif self.isEnabled and not (self.users or self.policy == 'enabled'):
            logger.debug( "Disabling %s", self.name )
            ts = time.time()
            yield self._disable()
            logger.info( "Disabled %s in %.1f seconds", self.name, time.time()-ts )
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

    @tasklet.tasklet
    def request( self, user ):
        assert self.policy in ['auto', 'enabled'], "Request for %s is not allowed" % ( self.name )
        assert user not in self.users, "User %s already requested %s" % ( user, self.name )
        self.users.append( user )
        yield self._update()
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )
        yield True

    @tasklet.tasklet
    def release( self, user ):
        assert user in self.users, "User %s did not request %s before releasing it" % ( user, self.name )
        self.users.remove( user )
        yield self._update()
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )

    @tasklet.tasklet
    def cleanup( self, user ):
        if user in self.users:
            yield self.release( user )
            logger.info( "Releasing %s for vanished user %s", self.name, user )

#----------------------------------------------------------------------------#
class DummyResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )

    @tasklet.tasklet
    def _enable( self ):
        yield None

    @tasklet.tasklet
    def _disable( self ):
        yield None

#----------------------------------------------------------------------------#
class ODeviceDResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )
        self.bus = dbus.SystemBus()

    @tasklet.tasklet
    def _enable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/PowerControl/" + self.name )
        iface = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        yield tasklet.WaitDBus( iface.SetPower, True)

    @tasklet.tasklet
    def _disable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/PowerControl/" + self.name )
        iface = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        yield tasklet.WaitDBus( iface.SetPower, False )

#----------------------------------------------------------------------------#
class OGPSDResource( AbstractResource ):
#----------------------------------------------------------------------------#
    def __init__( self, usageControl, name ):
        AbstractResource.__init__( self , usageControl, name )
        self.bus = dbus.SystemBus()

    @tasklet.tasklet
    def _enable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.ogpsd", "/org/freedesktop/Gypsy" )
        iface = dbus.Interface( proxy, "org.freesmartphone.GPS" )
        yield tasklet.WaitDBus( iface.SetPower, True )

    @tasklet.tasklet
    def _disable( self ):
        proxy = self.bus.get_object( "org.freesmartphone.ogpsd", "/org/freedesktop/Gypsy" )
        iface = dbus.Interface( proxy, "org.freesmartphone.GPS" )
        yield tasklet.WaitDBus( iface.SetPower, False )

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

    @tasklet.tasklet
    def _enable( self ):
        """Simply call the client Enable method"""
        yield tasklet.WaitDBus( self.obj.Enable )

    @tasklet.tasklet
    def _disable( self ):
        """Simply call the client Disable method"""
        yield tasklet.WaitDBus( self.obj.Disable )

    @tasklet.tasklet
    def _suspend( self ):
        """Simply call the client Suspend method"""
        yield tasklet.WaitDBus( self.obj.Suspend )

    @tasklet.tasklet
    def _resume( self ):
        """Simply call the client Resume method"""
        yield tasklet.WaitDBus( self.obj.Resume )

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
                resource.cleanup( old_owner ).start()

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

    @dbus.service.method( DBUS_INTERFACE, "s", "b", sender_keyword='sender', async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RequestResource( self, resourcename, sender, dbus_ok, dbus_error ):
        """Called by a client to request a resource

        This call will return imediatly, even if the resource need to perform
        some enabling actions.
        """
        self.resources[resourcename].request( sender ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "s", "", sender_keyword='sender', async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ReleaseResource( self, resourcename, sender, dbus_ok, dbus_error ):
        """Called by a client to release a previously requested resource

        This call will return imediatly, even if the resource need to perform
        some disabling actions.
        """
        self.resources[resourcename].release( sender ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "so", "", sender_keyword='sender' )
    def RegisterResource( self, resourcename, path, sender ):
        """Register a new resource from a client

        The client must provide a name for the resource, and a dbus object
        path to an object implementing org.freesmartphone.Resource interface
        """
        logger.info( "Register new resource %s", resourcename )
        resource = ClientResource( self, resourcename, path, sender )
        self.addResource( resource )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        """Suspend all the resources"""
        # Call the _suspend task connected to the dbus callbacks
        self._suspend().start_dbus( dbus_ok, dbus_error )

    @tasklet.tasklet
    def _suspend( self ):
        """The actual suspending tasklet"""
        logger.info( "suspending all resources" )
        for resource in self.resources.values():
            logger.debug( "suspending %s", resource.name )
            yield resource._suspend()

        # FIXME Play apmd and then use the sysfs interface
        os.system( "apm -s" )

        logger.info( "resuming all resources" )
        for resource in self.resources.values():
            logger.debug( "resuming %s", resource.name )
            yield resource._resume()

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
#    genericUsageControl.addResource( OGPSDResource( genericUsageControl, "GPS" ) )
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

