#!/usr/bin/env python
"""
Dummy Subsystem for Testing Purposes

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: testing
Module: testing
"""

MODULE_NAME = "testing"
__version__ = "0.0.0"

from framework import resource

import dbus
import dbus.service
import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

DBUS_INTERFACE = "org.freesmartphone.Testing"
DBUS_OBJECT_PATH = "/org/freesmartphone/Testing"

#============================================================================#
class Resource( resource.Resource ):
#============================================================================#
    def __init__( self, bus ):
        self.path = DBUS_OBJECT_PATH
        self.bus = bus
        dbus.service.Object.__init__( self, bus, self.path )
        resource.Resource.__init__( self, bus, "TEST" )
        logger.info("%s %s at %s initialized.", self.__class__.__name__, __version__, self.path )

        # default behaviour: everything works
        self.catmap = { "enabling":"ok",
                        "disabling":"ok",
                        "suspending":"ok",
                        "resuming":"ok" }

    #
    # framework.Resource
    #
    def _enable( self, on_ok, on_error ):
        logger.info( "enabling" )
        self._doit( "enabling" )

    def _disable( self, on_ok, on_error ):
        logger.info( "disabling" )
        self._doit( "disabling" )

    def _suspend( self, on_ok, on_error ):
        logger.info( "suspending" )
        self._doit( "suspending" )

    def _resume( self, on_ok, on_error ):
        logger.info("resuming")
        self._doit( "resuming" )

    def _doit( self, category, on_ok, on_error ):
        action = self.catmap[ category ]
        if action == "ok":
            on_ok()
        elif action == "error":
            on_error( "unspecified" )
        elif action == "veto":
            on_error( resource.SuspendVeto( "not allowed to suspend this resource" ) )
        else:
            foobar
    #
    # dbus interface
    #
    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetResourceBehaviour( self, category, behaviour, dbus_ok, dbus_error ):
        try:
            value = self.catmap[category]
        except KeyError:
            dbus_error( "unknown category, valid categories are: %s" % self.catmap.keys() )
        else:
            if behaviour not in "ok error veto".split():
                dbus_error( "unknown behaviour. valid behaviours are: ok error veto" )
            self.catmap[category] = str( behaviour )
            dbus_ok()

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    return [ Resource( controller.bus ) ]

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    pass

