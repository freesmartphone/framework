
# -*- coding: UTF-8 -*-
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: resource
"""

MODULE_NAME = "resource"
__version__ = "0.1.1"

import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import logging
import gobject

import framework

logger = logging.getLogger( MODULE_NAME )

class Resource( dbus.service.Object ):
    """Base class for all the resources
    
    The Resource class is used for anything that need to know about who is
    using a given resource. The ousaged subsystem manage all the resources and keep
    track of how many clients are using them. When a resource is no longer used,
    its Disable method will be called by ousaged. The resource objet can then do
    whatever is needed. When a resource is disabled and a client need to use it,
    ousaged will call its Enable method.
    
    A resource also needs to be able to prepare for a system suspend, or resume
    Ousaged will call the Suspend and Resume methods of the resource before a
    system suspend and after a system wakeup.
    
    To define a new resource, a subsystem need to subclass this class,
    and call the register method once after initialisation
    """
    DBUS_INTERFACE = 'org.freesmartphone.Resource'
        
    def __init__( self, bus, path, name=None ):
        """Register the object as a new resource in ousaged
        
        name is the name of the resource, that will be used by the clients.
        path is the dbus object path to this object.
        """
        super(Resource, self).__init__(bus, path)
        # We need to call the ousaged.Register method, but we can't do it
        # imediatly for the ousaged object may not be present yet.
        # We use gobject.idle_add method to make the call only at the next
        # mainloop iteration
        def on_idle():
            logger.info("register resource %s", name)
            # Here we are sure ousaged exists.
            bus = dbus.SystemBus()
            usaged = bus.get_object('org.freesmartphone.ousaged', '/org/freesmartphone/Usage')
            usaged = dbus.Interface(usaged, 'org.freesmartphone.Usage')
            def on_reply(*arg):
                pass
            def on_error(err):
                logger.error("An error occured when registering : %s", err)
            usaged.RegisterResource( name, self, reply_handler=on_reply, error_handler=on_error )
        
        gobject.idle_add(on_idle)
    
    # All the DBus methods will call the python implementation
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Enable( self, dbus_ok, dbus_error ):
        self._enable( dbus_ok, dbus_error )
        
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Disable( self, dbus_ok, dbus_error ):
        self._disable( dbus_ok, dbus_error )
        
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Suspend( self, dbus_ok, dbus_error ):
        self._suspend( dbus_ok, dbus_error )
        
    @dbus.service.method( DBUS_INTERFACE, "", "", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Resume( self, dbus_ok, dbus_error ):
        self._resume( dbus_ok, dbus_error ) 
        
    # Subclass of Service should reimplement those methods
    def _enable( self, on_ok, on_error ):
        on_ok()
        
    def _disable( self, on_ok, on_error ):
        on_ok()
        
    def _suspend( self, on_ok, on_error ):
        on_ok()
        
    def _resume( self, on_ok, on_error ):
        on_ok()
