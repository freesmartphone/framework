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
__version__ = "0.7.1"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

from .resources import ClientResource
from .lowlevel import resumeReason

import framework.patterns.tasklet as tasklet

import gobject
import dbus
import dbus.service

import time, os, subprocess

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
# DBus Exceptions specifications specific to this module

class ResourceUnknown( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceUnknown"

class ResourceExists( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceExists"

class ResourceInUse( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Usage.ResourceInUse"

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
        self.SystemAction( "suspend" ) # send as early as possible

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
        # ---------------> Good Night!
        reason = resumeReason()
        # ---------------< Good Morning!
        logger.info( "kernel has resumed - reason = %s" % reason )

        if reason == "LowBattery":
            logger.info( "kernel resumed because of low battery. Emergency Shutdown!" )
            subprocess.call( "shutdown -h now &", shell=True )
            # FIXME trigger shutdown quit
            yield None
        else:
            logger.info( "resuming resources..." )
            for resource in self.resources.values():
                logger.debug( "resuming %s", resource.name )
                yield resource._resume()
            logger.info( "...completed." )

            gobject.idle_add( lambda self=self:self.SystemAction( "resume" ) and False ) # send as late as possible

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

    @dbus.service.method( DBUS_INTERFACE, "so", "",
                          sender_keyword='sender',
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
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

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        """
        Suspend all resources and the system.
        """
        # Call the _suspend task connected to the dbus callbacks
        self._suspend().start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Shutdown( self, dbus_ok, dbus_error ):
        """
        Shutdown the system.
        """
        logger.info( "System shutting down..." )
        self.SystemAction( "shutdown" ) # send signal
        dbus_ok()
        # FIXME this is not a clean shutdown
        subprocess.call( "shutdown -h now &", shell=True )

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Reboot( self, dbus_ok, dbus_error ):
        """
        Reboot the system.
        """
        logger.info( "System rebooting..." )
        # FIXME should we cleanly shutdown resources here -- will it matter?
        self.SystemAction( "reboot" ) # send signal
        dbus_ok()
        subprocess.call( "reboot &", shell=True )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sba{sv}" )
    def ResourceChanged( self, resourcename, state, attributes ):
        pass

    @dbus.service.signal( DBUS_INTERFACE, "sb" )
    def ResourceAvailable( self, resourcename, state ):
        pass

    @dbus.service.signal( DBUS_INTERFACE, "s" )
    def SystemAction( self, action ):
        pass

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ GenericUsageControl( controller.bus ) ]

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    pass