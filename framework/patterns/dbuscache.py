#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: controller
"""

__version__ = "1.0.0"

import dbus

_bus = dbus.SystemBus()
_objects = {}
_ifaces = {}

def dbusInterfaceForObjectWithInterface( service, object, interface ):
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
            obj = _objects[ ( service, object ) ] = _bus.get_object( service, object, introspect=False, follow_name_owner_changes=False )
        iface = _ifaces[ ( service, object, interface ) ] = dbus.Interface( obj, interface )

    return iface

dbus.InterfaceForObjectWithInterface = dbusInterfaceForObjectWithInterface
