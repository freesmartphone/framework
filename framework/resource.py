# -*- coding: UTF-8 -*-
"""
freesmartphone.org Framework Daemon

(C) 2008 Guillaume 'Charlie' Chereau <charlie@openmoko.org>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: resource
"""

MODULE_NAME = "frameworkd.resource"
__version__ = "0.1.2"

import dbus, dbus.service

import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class Resource( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """
    Base class for all the resources

    The Resource class is used for anything that need to know about who is
    using a given resource. The OUsaged subsystem manage all the resources and keep
    track of how many clients are using them. When a resource is no longer used,
    its Disable method will be called by ousaged. The resource objet can then do
    whatever is needed. When a resource is disabled and a client need to use it,
    ousaged will call its Enable method.

    A resource also needs to be able to prepare for a system suspend, or resume
    OUsaged will call the Suspend and Resume methods of the resource before a
    system suspend and after a system wakeup.

    To define a new resource, a subsystem needs to subclass this class,
    and call the register method once after initialisation.
    """
    DBUS_INTERFACE = 'org.freesmartphone.Resource'

    def __init__( self, bus, path, name=None ):
        """
        Register the object as a new resource in ousaged

        name is the name of the resource, that will be used by the clients.
        path is the dbus object path to this object.
        """
        super( Resource, self ).__init__( bus, path )

        self._resourceBus = bus
        self._resourceName = name
        self._resourceStatus = "disabled"

        # We need to call the ousaged.Register method, but we can't do it
        # imediatly for the ousaged object may not be present yet.
        # We use gobject.idle_add method to make the call only at the next
        # mainloop iteration
        def on_idle( self ):
            logger.info( "Trying to register resource %s", self._resourceName )
            # Here we are sure ousaged exists, if it has not been disabled
            try:
                usaged = self.bus.get_object( "org.freesmartphone.ousaged", "/org/freesmartphone/Usage" )
            except dbus.exceptions.DBusException:
                logger.warning( "Can't register resource %s -- ousaged is not present", name )
            else:
                usaged = dbus.Interface( usaged, "org.freesmartphone.Usage" )
                def on_reply( *arg ):
                    pass
                def on_error( err ):
                    logger.error( "An error occured when registering: %s", err )
                usaged.RegisterResource( self._resourceName, self, reply_handler=on_reply, error_handler=on_error )

        gobject.idle_add( on_idle, self )

    def _updateResourceStatus( self, nextStatus ):
        logger.info( "setting resource status for %s from %s to %s" % ( self._resourceName, self._resourceStatus, nextStatus ) )
        self._resourceStatus = nextStatus

    # callback factory
    def cbFactory( self, next, dbus_callback ):
        def status_callback( self=self, next=next, dbus_callback=dbus_callback ):
            self._updateResourceStatus( next )
            dbus_callback()
        return status_callback

    # The DBus methods update the resource status and call the python implementation
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Enable( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "enabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error )
        self._updateResourceStatus( "enabling" )
        self._enable( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Disable( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "disabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error )
        self._updateResourceStatus( "disabling" )
        self._disable( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "suspended", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error )
        self._updateResourceStatus( "suspending" )
        self._suspend( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Resume( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "enabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error )
        self._updateResourceStatus( "resuming" )
        self._resume( ok_callback, err_callback )

    # Subclass of Service should reimplement these methods
    def _enable( self, on_ok, on_error ):
        logger.warning( "FIXME: Override Resource._enable for resource %s", self._resourceName )
        on_ok()

    def _disable( self, on_ok, on_error ):
        logger.warning( "FIXME: Override Resource._disable for resource %s", self._resourceName )
        on_ok()

    def _suspend( self, on_ok, on_error ):
        logger.warning( "FIXME: Override Resource._suspend for resource %s", self._resourceName )
        on_ok()

    def _resume( self, on_ok, on_error ):
        logger.warning( "FIXME: Override Resource._resume for resource %s", self._resourceName )
        on_ok()
