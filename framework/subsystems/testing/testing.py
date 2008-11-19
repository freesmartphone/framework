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

DBUS_INTERFACE_NETWORK = "org.freesmartphone.Testing"
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
    #
    # framework.Resource
    #
    def _enable( self, on_ok, on_error ):
        logger.info( "enabling" )
        on_ok()

    def _disable( self, on_ok, on_error ):
        logger.info( "disabling" )
        on_ok()

    def _suspend( self, on_ok, on_error ):
        logger.info( "suspending" )
        on_ok()

    def _resume( self, on_ok, on_error ):
        logger.info("resuming")
        on_ok()

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    return [ Resource( controller.bus ) ]

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    pass

