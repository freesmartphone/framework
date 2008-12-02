#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic reference counted Resource Management

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ousaged
Module: generic
"""

MODULE_NAME = "ousaged"
__version__ = "0.6.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

import framework.patterns.tasklet as tasklet

import gobject
import dbus
import dbus.service

import time, os

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
# DBus Exceptions specifications specific to this module

class PolicyUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.PolicyUnknown"

class PolicyDisabled( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.PolicyDisabled"

class ResourceUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceUnknown"

class ResourceExists( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceExists"

class ResourceInUse( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceInUse"

class UserExists( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.UserExists"

class UserUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.UserUnknown"

#----------------------------------------------------------------------------#
class AbstractResource( object ):
#----------------------------------------------------------------------------#
    """
    Abstract base class for a resource.

    This is the internal class used by the resource manager to keep track of a resource.
    Every resource has a name, a list of current users, and a policy.

    Valid policies are:
        * auto: Reference counted, this is the default,
        * disabled: The resource is always off,
        * enabled: The resource is always on.
    """

    VALID_POLICIES = "disabled auto enable".split()

    def __init__( self, usageControl, name = "Abstract" ):
        """
        Create a new resource

        `usageControl` : the resource controler object that will handle this resource
        `name` : the name of the resource
        """
        self.usageControl = usageControl
        self.name = str(name)
        self.users = []
        self.policy = 'auto'
        self.isEnabled = False

    @tasklet.tasklet
    def _enable( self ):
        """
        Enable the resource.
        """
        yield None

    @tasklet.tasklet
    def _disable( self ):
        """
        Disable the resource.
        """
        yield None

    @tasklet.tasklet
    def _suspend( self ):
        """
        Called before the system is going to suspend.
        """
        yield None

    @tasklet.tasklet
    def _resume( self ):
        """
        Called after a system resume.
        """
        yield None

    @tasklet.tasklet
    def _update( self ):
        if not self.isEnabled and ( self.users or self.policy == 'enabled' ):
            logger.debug( "Enabling %s", self.name )
            ts = time.time()
            yield self._enable()
            logger.info( "Enabled %s in %.1f seconds", self.name, time.time()-ts )
            self.isEnabled = True
        elif self.isEnabled and not ( self.users or self.policy == 'enabled' ):
            logger.debug( "Disabling %s", self.name )
            ts = time.time()
            yield self._disable()
            logger.info( "Disabled %s in %.1f seconds", self.name, time.time()-ts )
            self.isEnabled = False

    @tasklet.tasklet
    def setPolicy( self, policy ):
        if not policy in AbstractResource.VALID_POLICIES:
            raise PolicyUnknown( "Unknown resource policy. Valid policies are %s" % AbstractResource.VALID_POLICIES )
        if self.users:
            if policy == "disabled":
                raise ResourceInUse( "Can't disable %s. Current users are: %s" % ( self.name, self.users ) )
        if self.policy != policy:
            self.policy = policy
            yield self._update()
            self.usageControl.ResourceChanged(
                self.name, self.isEnabled, { "policy": self.policy, "refcount": len( self.users ) }
            )

    @tasklet.tasklet
    def request( self, user ):
        if not self.policy in [ 'auto', 'enabled' ]:
            raise PolicyDisabled( "Requesting %s not allowed by resource policy." % ( self.name ) )
        if user in self.users:
            raise UserExists( "User %s already requested %s" % ( user, self.name ) )
        self.users.append( user )
        yield self._update()
        self.usageControl.ResourceChanged(
            self.name, self.isEnabled, {"policy": self.policy, "refcount": len( self.users )}
        )

    @tasklet.tasklet
    def release( self, user ):
        if not user in self.users:
            raise UserUnknown( "User %s did not request %s before releasing it" % ( user, self.name ) )
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
    """
    This is a dummy resource class that does nothing.
    """
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
    """
    This is a resource class for objects controlled by the odeviced subsystem.
    """
    DEPRECATED = True

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
class ClientResource( AbstractResource ):
#----------------------------------------------------------------------------#
    """A resource that is controled by an external client.

    The client needs to expose a dbus object implementing org.freesmartphone.Resource.
    It can register using the RegisterResource of /org/freesmartphone/Usage.
    If the client is written in python, it can use the framework.Resource class.
    """
    def __init__( self, usageControl, name, path, sender ):
        """
        Create a new ClientResource

        Only the resource manager should call this method
        """
        super( ClientResource, self ).__init__( usageControl, name )
        bus = dbus.SystemBus()
        proxy = bus.get_object( sender, path )
        self.iface = dbus.Interface( proxy, "org.freesmartphone.Resource" )

    @tasklet.tasklet
    def _enable( self ):
        """Simply call the client Enable method"""
        yield tasklet.WaitDBus( self.iface.Enable )

    @tasklet.tasklet
    def _disable( self ):
        """Simply call the client Disable method"""
        yield tasklet.WaitDBus( self.iface.Disable )

    @tasklet.tasklet
    def _suspend( self ):
        """Simply call the client Suspend method"""
        yield tasklet.WaitDBus( self.iface.Suspend )

    @tasklet.tasklet
    def _resume( self ):
        """Simply call the client Resume method"""
        yield tasklet.WaitDBus( self.iface.Resume )

#----------------------------------------------------------------------------#
class GenericUsageControl( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """
    A Dbus Object implementing org.freesmartphone.Usage.
    """
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX

    def __init__( self, bus ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        dbus.service.Object.__init__( self, bus, self.path )
        self.resources = {}
        bus.add_signal_receiver(
            self._nameOwnerChangedHandler,
            "NameOwnerChanged",
            dbus.BUS_DAEMON_IFACE,
            dbus.BUS_DAEMON_NAME,
            dbus.BUS_DAEMON_PATH
        )
        logger.info( "%s initialized. Serving %s at %s", self.__class__.__name__, self.interface, self.path )

    def _addResource( self, resource ):
        if not self.resources.get(resource.name, None) is None:
            raise ResourceExists( "Resource %s already registered" % resource.name )
        self.resources[resource.name] = resource
        self.ResourceAvailable( resource.name, True )

    def _getResource( self, resourcename ):
        r = self.resources.get(resourcename, None)
        if r is None:
            raise ResourceUnknown( "Unknown resource %s" % resourcename )
        return r

    @tasklet.tasklet
    def _suspend( self ):
        """
        The actual suspending tasklet, phase 1 (suspending resources)
        """
        logger.info( "suspending all resources..." )
        for resource in self.resources.values():
            logger.debug( "suspending %s", resource.name )
            yield resource._suspend()
        logger.info( "...completed" )

        # FIXME is this additional indirection necessary?
        gobject.idle_add( self._suspend2 )

    def _suspend2( self ):
        self._kernelSuspendAndResume().start()
        return False

    @tasklet.tasklet
    def _kernelSuspendAndResume( self ):
        """
        The actual resuming tasklet.
        """
        # FIXME might want to traverse /etc/apm.d/... and launch them scripts

        logger.info( "triggering kernel suspend" )
        open( "/sys/power/state", "w" ).write( "mem\n" )

        logger.info( "kernel has resumed - resuming resources..." )
        for resource in self.resources.values():
            logger.debug( "resuming %s", resource.name )
            yield resource._resume()
        logger.info( "...completed." )

    def _nameOwnerChangedHandler( self, name, old_owner, new_owner ):
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
        return self._getResource( resourcename ).users

    @dbus.service.method( DBUS_INTERFACE, "s", "b" )
    def GetResourceState( self, resourcename ):
        return self._getResource( resourcename ).isEnabled

    @dbus.service.method( DBUS_INTERFACE, "s", "s" )
    def GetResourcePolicy( self, resourcename ):
        return self._getResource( resourcename ).policy

    @dbus.service.method( DBUS_INTERFACE, "ss", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetResourcePolicy( self, resourcename, policy, dbus_ok, dbus_error ):
        self._getResource( resourcename ).setPolicy( policy ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "s", "", sender_keyword='sender', async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RequestResource( self, resourcename, sender, dbus_ok, dbus_error ):
        """
        Called by a client to request a resource.

        This call will return imediatly, even if the resource need to perform
        some enabling actions.
        """
        try:
            resource = self.resources[resourcename]
        except KeyError:
            dbus_error( ResourceUnknown( "Known resources are %s" % self.resources.keys() ) )
        else:
            resource.request( sender ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "s", "", sender_keyword='sender', async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ReleaseResource( self, resourcename, sender, dbus_ok, dbus_error ):
        """
        Called by a client to release a previously requested resource.

        This call will return imediatly, even if the resource need to perform
        some disabling actions.
        """
        try:
            resource = self.resources[resourcename]
        except KeyError:
            dbus_error( ResourceUnknown( "Known resources are %s" % self.resources.keys() ) )
        else:
            resource.release( sender ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "so", "", sender_keyword='sender', async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RegisterResource( self, resourcename, path, sender, dbus_ok, dbus_error ):
        """
        Register a new resource from a client.

        The client must provide a name for the resource, and a dbus object
        path to an object implementing org.freesmartphone.Resource interface.
        """
        if resourcename in self.resources:
            dbus_error( ResourceExists( "Resource %s already exists" % resourcename ) )
        else:
            logger.info( "Register new resource %s", resourcename )
            resource = ClientResource( self, resourcename, path, sender )
            self._addResource( resource )
            dbus_ok()

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        """
        Suspend all the resources.
        """
        # Call the _suspend task connected to the dbus callbacks
        self._suspend().start_dbus( dbus_ok, dbus_error )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sba{sv}" )
    def ResourceChanged( self, resourcename, state, attributes ):
        pass

    @dbus.service.signal( DBUS_INTERFACE, "sb" )
    def ResourceAvailable( self, resourcename, state ):
        pass

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ GenericUsageControl( controller.bus ) ]

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
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

