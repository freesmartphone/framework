#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: framework
Module: controller
"""

__version__ = "1.0.2"

import dbus

_bus = dbus.SystemBus()
_objects = {}
_ifaces = {}

#----------------------------------------------------------------------------#
def dbusInterfaceForObjectWithInterface( service, object, interface ):
#----------------------------------------------------------------------------#
    """
    Gather dbus.Interface proxy for given triple of service, object, interface
    Try to cache as much as possible.
    """

    try:
        iface = _ifaces[ ( service, object, interface ) ]
    except KeyError:
        try:
            obj = _objects[ ( service, object ) ]
        except KeyError:
            # this call will always succeed, even if the questioned service is not online yet
            obj = _objects[ ( service, object ) ] = _bus.get_object( service, object, introspect=False, follow_name_owner_changes=True )
        iface = _ifaces[ ( service, object, interface ) ] = dbus.Interface( obj, interface )

    return iface

dbus.InterfaceForObjectWithInterface = dbusInterfaceForObjectWithInterface

#----------------------------------------------------------------------------#
def dbusCallAsyncDontCare( method, *args ):
#----------------------------------------------------------------------------#
    """
    Call dbus method async., don't care about any errors or replies.
    """
    method( *args, **dict( reply_handler=nop, error_handler=nop ) )


#----------------------------------------------------------------------------#
def nop( *args, **kwargs ):
#----------------------------------------------------------------------------#
    #print ( "dbusCallAsyncDontCare returned with ", args, kwargs )
    pass



