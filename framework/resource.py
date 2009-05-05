# -*- coding: UTF-8 -*-
"""
freesmartphone.org Framework Daemon

(C) 2008 Guillaume 'Charlie' Chereau <charlie@openmoko.org>
(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: resource
"""

MODULE_NAME = "frameworkd.resource"
__version__ = "0.5.2"

from framework.config import config
from framework.patterns import decorator, asyncworker

import gobject
import dbus.service
from dbus import validate_interface_name, Signature, validate_member_name

import Queue

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
@decorator.decorator
def checkedmethod(f, *args, **kw):
    """
    This decorator wraps an asynchronous dbus method to checks the resource status and returning
    org.freesmartphone.Resource.ResourceNotEnabled if the resource is not enabled.
    """
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    dbus_error = args[-1]
    if self._resourceStatus == "enabled":
        return f(*args, **kw)
    else:
        dbus_error( ResourceNotEnabled( "Resource %s is not enabled, current status is '%s'" % ( self.__class__.__name__, self._resourceStatus ) ) )

#----------------------------------------------------------------------------#
@decorator.decorator
def checkedsyncmethod(f, *args, **kw):
    """
    This decorator wraps a synchronous dbus method to checks the resource status and returning
    org.freesmartphone.Resource.ResourceNotEnabled if the resource is not enabled.
    """
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    if self._resourceStatus == "enabled":
        return f(*args, **kw)
    else:
        dbus_error( ResourceNotEnabled( "Resource %s is not enabled, current status is '%s'" % ( self.__class__.__name__, self._resourceStatus ) ) )

#----------------------------------------------------------------------------#
@decorator.decorator
def queuedsignal(f, *args, **kw):
    """
    This decorator wraps a dbus signal and sends it only if the resource is enabled.
    Otherwise, it enqueues the signal.
    """
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    if self._resourceStatus == "enabled":
        return f(*args, **kw)
    else:
        self._delayedSignalQueue.put( ( f, args ) ) # push for later

#----------------------------------------------------------------------------#
@decorator.decorator
def checkedsignal(f, *args, **kw):
    """
    This decorator wraps a dbus signal and sends it only if the resource is enabled.
    Otherwise, it drops the signal.
    """
    #print "calling %s with args %s, %s" % (f.func_name, args, kw)
    self = args[0]
    if self._resourceStatus == "enabled":
        return f(*args, **kw)
    else:
        logger.info( "Dropping signal %s, since resource %s is not enabled. Current status is '%s'" % ( f.__name__, self.__class__.__name__, self._resourceStatus ) )

#----------------------------------------------------------------------------#
class ResourceNotEnabled( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Resource.NotEnabled"

#----------------------------------------------------------------------------#
class ResourceError( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Resource.Error"

#----------------------------------------------------------------------------#
class Resource( dbus.service.Object, asyncworker.SynchronizedAsyncWorker ):
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

    sync_resources_with_lifecycle = config.getValue( "ousaged", "sync_resources_with_lifecycle", "always" )

    commandInProgress = { \
        "enable":   "enabling",
        "disable":  "disabling",
        "suspend":  "suspending",
        "resume":   "resuming",
        }

    commandDone = { \
        "enable":   "enabled",
        "disable":  "disabled",
        "suspend":  "suspended",
        "resume":   "enabled",
        }

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
        self._resourceStatus = "unknown"
        self._delayedSignalQueue = Queue.Queue()

        asyncworker.SynchronizedAsyncWorker.__init__( self )

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
                gobject.idle_add( self.Enable, lambda: False, lambda dummy: False )
            else:
                usaged = dbus.Interface( usaged, "org.freesmartphone.Usage" )
                def on_reply( *arg ):
                    pass
                def on_error( err ):
                    logger.error( "An error occured when registering: %s", err )
                usaged.RegisterResource( self._resourceName, self, reply_handler=on_reply, error_handler=on_error )
            return False # mainloop: don't call me again

        gobject.idle_add( on_idle, self )

    def onProcessElement( self, element ):
        command, ok_callback, err_callback = element
        logger.debug( "processing command '%s' for resource '%s' (present status=%s)", command, self, self._resourceStatus )

        stateNow = self._resourceStatus
        if stateNow == "disabled" and command != "enable":
            ok_callback()
        else:

            def ok( self=self, command=command, dbus_ok=ok_callback ):
                self._updateResourceStatus( self.commandDone[command] )
                logger.debug( "(ok) done processing command '%s' for resource '%s' (new status=%s); triggering next command", command, self, self._resourceStatus )
                self.trigger()
                dbus_ok()

            def err( error, self=self, command=command, dbus_err=err_callback ):
                logger.debug( "(error) done processing command '%s' for resource '%s' (new status=%s); triggering next command", command, self, self._resourceStatus )
                self.trigger()
                dbus_err( error )

            self._updateResourceStatus( self.commandInProgress[command] )
            if command == "enable":
                self._enable( ok, err )
            elif command == "disable":
                self._disable( ok, err )
            elif command == "suspend":
                self._suspend( ok, err )
            elif command == "resume":
                self._resume( ok, err )
            else:
                logger.warning( "unknown resource command '%s' ignored.", command )
                self.trigger()

    def shutdown( self ):
        """
        Called by the subsystem during system shutdown.
        """

        if self.sync_resources_with_lifecycle in ( "always", "shutdown" ) and \
           self._resourceStatus in ( "enabled" , "enabling", "unknown" ):
            # no error handling, either it works or not
            #self._disable( lambda: None, lambda Foo: None )
            self.Disable( lambda: None, lambda Foo: None )

    def _updateResourceStatus( self, nextStatus ):
        logger.info( "setting resource status for %s from %s to %s" % ( self._resourceName, self._resourceStatus, nextStatus ) )
        self._resourceStatus = nextStatus
        # send all queued signals, if any
        if self._resourceStatus == "enabled":
            logger.debug( "resource now enabled. checking signal queue" )
            while not self._delayedSignalQueue.empty():
                f, args = self._delayedSignalQueue.get()
                logger.debug( "sending delayed signal %s( %s )", f, args )
                f(*args)

    # The DBus methods update the resource status and call the python implementation
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Enable( self, dbus_ok, dbus_error ):
        self.enqueue( "enable", dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Disable( self, dbus_ok, dbus_error ):
        self.enqueue( "disable", dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        self.enqueue( "suspend", dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Resume( self, dbus_ok, dbus_error ):
        self.enqueue( "resume", dbus_ok, dbus_error )

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
