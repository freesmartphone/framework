#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic reference counted Resource Management

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ousaged
Module: resources
"""

MODULE_NAME = "ousaged"
__version__ = "0.6.2"

from framework.config import config
from framework.patterns import tasklet, dbuscache

import gobject
import dbus
import dbus.service

import time, os, subprocess

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
# DBus Exceptions specifications specific to this module

class PolicyUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.PolicyUnknown"

class PolicyDisabled( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.PolicyDisabled"

class UserExists( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.UserExists"

class UserUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.UserUnknown"

class ResourceInUse( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceInUse"

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

    VALID_POLICIES = "disabled auto enabled".split()

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
    """
    A resource controlled by an external client.

    The client needs to expose a dbus object implementing org.freesmartphone.Resource.
    It can register using the RegisterResource of /org/freesmartphone/Usage.
    If the client is written in python, it can use the framework.Resource class.
    """
    sync_resources_with_lifecycle = config.getValue( "ousaged", "sync_resources_with_lifecycle", "always" )

    def __init__( self, usageControl, name, path, sender ):
        """
        Create a new ClientResource

        Only the resource manager should call this method
        """
        super( ClientResource, self ).__init__( usageControl, name )

        self.path = path
        self.sender = sender
        self.iface = None

        if self.sync_resources_with_lifecycle in ( "always", "startup" ):
            self._disable().start()

    @tasklet.tasklet
    def _enable( self ):
        """Simply call the client Enable method"""
        if self.iface is None:
            self.iface = dbuscache.dbusInterfaceForObjectWithInterface( self.sender, self.path, "org.freesmartphone.Resource" )
        yield tasklet.WaitDBus( self.iface.Enable )

    @tasklet.tasklet
    def _disable( self ):
        """Simply call the client Disable method"""
        if self.iface is None:
            self.iface = dbuscache.dbusInterfaceForObjectWithInterface( self.sender, self.path, "org.freesmartphone.Resource" )
        yield tasklet.WaitDBus( self.iface.Disable )

    @tasklet.tasklet
    def _suspend( self ):
        """Simply call the client Suspend method"""
        if self.iface is None:
            self.iface = dbuscache.dbusInterfaceForObjectWithInterface( self.sender, self.path, "org.freesmartphone.Resource" )
        yield tasklet.WaitDBus( self.iface.Suspend )

    @tasklet.tasklet
    def _resume( self ):
        """Simply call the client Resume method"""
        if self.iface is None:
            self.iface = dbuscache.dbusInterfaceForObjectWithInterface( self.sender, self.path, "org.freesmartphone.Resource" )
        yield tasklet.WaitDBus( self.iface.Resume )

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    pass
