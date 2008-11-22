#!/usr/bin/env python
"""
Network Connection Sharing

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: onetworkd
Module: sharing
"""

MODULE_NAME = "onetworkd"
__version__ = "0.0.0"

import dbus
import dbus.service
import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

DBUS_INTERFACE_NETWORK = "org.freesmartphone.Network"
DBUS_OBJECT_PATH = "/org/freesmartphone/Network"

#============================================================================#
class ConnectionSharing(dbus.service.Object):
#============================================================================#
    def __init__( self, bus ):
        self.path = DBUS_OBJECT_PATH
        dbus.service.Object.__init__( self, bus, self.path )
        self.bus = bus

    #
    # dbus org.freesmartphone.Network
    #
    @dbus.service.method( DBUS_INTERFACE_NETWORK, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ShareConnectionsForInterface( self, interface, dbus_ok, dbus_error ):
        # enable forwarding and launch dhcp server listening on said interface
        dbus_ok()

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    return [ ConnectionSharing( controller.bus ) ]

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    pass

