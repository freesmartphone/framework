#!/usr/bin/env python
"""
Open Device Daemon - Abstract Power and Resource Management Classes

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: odeviced
Module: powercontrol
"""

__version__ = "0.0.0"
MODULE_NAME = "odeviced.powercontrol"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile
from framework import resource

import dbus.service
import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class GenericPowerControl( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """
    An abstract Dbus Object implementing org.freesmartphone.Device.PowerControl.
    """
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, name, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/PowerControl/%s" % name
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        self.name = name
        self.powernode = None
        self.resetnode = None
        self.onValue = "1"
        self.offValue = "0"

    #
    # default implementations, feel free to override in descendants
    #
    def getPower( self ):
        return int( readFromFile( self.powernode ) )

    def setPower( self, power ):
        value = self.onValue if power else self.offValue
        writeToFile( self.powernode, value )

    def reset( self ):
        writeToFile( self.resetnode, "1" )

    def sendPowerSignal( self, expectedPower ):
        if self.getPower() == expectedPower:
            self.Power( self.name, expectedPower )
        else:
            logger.warning( "%s expected a power change for %s to %s which didn't happen" % ( __name__, self.name, expectedPower ) )
        return False # mainloop: don't call me again

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.name

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def GetPower( self ):
        return self.getPower()

    @dbus.service.method( DBUS_INTERFACE, "b", "" )
    def SetPower( self, power ):
        if power != self.getPower():
            self.setPower( power )
            gobject.timeout_add_seconds( 3, lambda self=self: self.sendPowerSignal( power ) )
        else:
            # FIXME should we issue an error here or just silently ignore?
            pass

    @dbus.service.method( DBUS_INTERFACE, "", "" )
    def Reset( self ):
        self.reset()

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sb" )
    def Power( self, device, power ):
        logger.info( "%s power for %s changed to %s" % ( __name__, self.name, power ) )

#----------------------------------------------------------------------------#
class ResourceAwarePowerControl( GenericPowerControl, resource.Resource ):
#----------------------------------------------------------------------------#
    """
    Resource object that maps enabling/disabling/suspending/resuming to
    the simple power on/off operations provided by GenericPowerControl.
    """

    def __init__( self, bus, name, node ):
        GenericPowerControl.__init__( self, bus, name, node )
        resource.Resource.__init__( self, bus, name )

    def _enable( self, on_ok, on_error ):
        self.SetPower( True )
        on_ok()

    def _disable( self, on_ok, on_error ):
        self.SetPower( False )
        on_ok()

    def _suspend( self, on_ok, on_error ):
        self._disable( on_ok, on_error )

    def _resume( self, on_ok, on_error ):
        self._enable( on_ok, on_error )

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    pass
