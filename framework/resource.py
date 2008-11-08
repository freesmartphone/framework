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
__version__ = "0.3.0"

from framework.patterns import decorator

import gobject
import dbus.service
from dbus import validate_interface_name, Signature, validate_member_name

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
@decorator.decorator
def checkedmethod(f, *args, **kw):
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    dbus_error = args[-1]
    if self._resourceStatus != "disabled":
        return f(*args, **kw)
    else:
        dbus_error( ResourceNotEnabled )

#----------------------------------------------------------------------------#
@decorator.decorator
def checkedsyncmethod(f, *args, **kw):
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    if self._resourceStatus != "disabled":
        return f(*args, **kw)
    else:
        raise ResourceNotEnabled()

#----------------------------------------------------------------------------#
class ResourceNotEnabled( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Resource.NotEnabled"

#----------------------------------------------------------------------------#
class Resource( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """
    Base class for all the resources

    The Resource class is used for anything that need to know about who is
    using a given resource. The OUsaged subsystem manage all the resources and keep
    track of how many clients are using them. When a resource is no longer used,
    its Disable method will be called by ousaged. The resource object can then do
    whatever is needed. When a resource is disabled and a client need to use it,
    ousaged will call its Enable method.

    A resource also needs to be able to prepare for a system suspend, or resume
    OUsaged will call the Suspend and Resume methods of the resource before a
    system suspend and after a system wakeup.

    To define a new resource, a subsystem needs to subclass this class,
    and call the register method once after initialisation.
    """
    DBUS_INTERFACE = 'org.freesmartphone.Resource'

    def __init__( self, bus, name ):
        """
        Register the object as a new resource in ousaged

        bus: dbus session bus
        name: the name of the resource that will be used by the clients
        """
        # HACK HACK HACK: We do _not_ initialize the dbus service object here,
        # (in order to prevent initializing it twice), but rather rely on someone
        # else doing this for us.
        if not isinstance( self, dbus.service.Object ):
            raise RuntimeError( "Resource only allowed as mixin w/ dbus.service.Object" )
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
                usaged = self._resourceBus.get_object( "org.freesmartphone.ousaged", "/org/freesmartphone/Usage" )
            except dbus.exceptions.DBusException:
                logger.warning( "Can't register resource %s since ousaged is not present. Enabling device", name )
                gobject.idle_add( self.Enable, lambda: None, lambda dummy: None )
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
    def cbFactory( self, next, dbus_callback, *args ):
        def status_callback( self=self, next=next, dbus_callback=dbus_callback, *args ):
            self._updateResourceStatus( next )
            dbus_callback( *args )
        return status_callback

    # The DBus methods update the resource status and call the python implementation
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Enable( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "enabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error, "could not enable resource" )
        self._updateResourceStatus( "enabling" )
        self._enable( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Disable( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "disabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error, "could not disable resource" )
        self._updateResourceStatus( "disabling" )
        self._disable( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "suspended", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error, "could not suspend resource" )
        # FIXME: What do we do if status is disabling?
        if self._resourceStatus == "disabled":
            dbus_ok()
        else:
            self._updateResourceStatus( "suspending" )
            self._suspend( ok_callback, err_callback )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Resume( self, dbus_ok, dbus_error ):
        ok_callback = self.cbFactory( "enabled", dbus_ok )
        err_callback = self.cbFactory( self._resourceStatus, dbus_error, "could not resume resource" )
        if self._resourceStatus == "disabled":
            dbus_ok()
        else:
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
