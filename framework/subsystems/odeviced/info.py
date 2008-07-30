#!/usr/bin/env python
"""
Open Device Daemon - A plugin for gathering device information

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.1.1"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile

import dbus.service
import ConfigParser

import logging
logger = logging.getLogger( "odeviced.info" )

#----------------------------------------------------------------------------#
class Info( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Info"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Info"

    def __init__( self, bus, config, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Info"
        dbus.service.Object.__init__( self, bus, self.path )
        self.config = config
        logger.info( "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetCpuInfo( self ):
        cpuinfo = readFromFile( "/proc/cpuinfo" ).split( '\n' )
        d = {}
        for line in cpuinfo:
            try:
                key, value = line.split( ':' )
            except ValueError: # no valid line
                continue
            d[key.strip()] = value.strip()
        return d

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""

    return [ Info( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
