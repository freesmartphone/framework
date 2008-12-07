#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd
Module: server
"""

MODULE_NAME = "ogsmd.server"
__version__ = "0.1.0"

from framework import resource

import dbus
import dbus.service
from dbus import DBusException

from gobject import timeout_add, idle_add
import weakref
import math
import sys, os
import types

import logging
logger = logging.getLogger( MODULE_NAME )

from device import DBUS_INTERFACE_DEVICE, \
                   DBUS_OBJECT_PATH_DEVICE, \
                   DBUS_BUS_NAME_DEVICE, \
                   DBUS_INTERFACE_SIM, \
                   DBUS_INTERFACE_CB

DBUS_INTERFACE_NETWORK = "org.freesmartphone.Network"
DBUS_INTERFACE_HZ = "org.freesmartphone.GSM.HZ"
DBUS_OBJECT_PATH_SERVER = "/org/freesmartphone/GSM/Server"

HOMEZONE_DEBUG = False

#=========================================================================#
class Server( dbus.service.Object ):
#=========================================================================#
    """
    Open Phone Server aggregated functions:
    - HomeZone

    Ideas:
    - watch for clients on bus and send coldplug status
    - monitor device aliveness and restart, if necessary
    """

    def __init__( self, bus ):
        self.path = DBUS_OBJECT_PATH_SERVER
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized." % ( self.__class__.__name__, __version__ ) )
        self.bus = bus
        self.homezones = None
        self.zone = "unknown"
        self.setupSignals()

    def setupSignals( self ):
        device = self.bus.get_object( DBUS_BUS_NAME_DEVICE, DBUS_OBJECT_PATH_DEVICE )
        self.fso_cb = dbus.Interface( device, DBUS_INTERFACE_CB )
        self.fso_cb.connect_to_signal( "IncomingCellBroadcast", self.onIncomingCellBroadcast )
        self.fso_sim = dbus.Interface( device, DBUS_INTERFACE_SIM )

    def __del__( self ):
        server = None

    #
    # Callbacks
    #
    def onIncomingCellBroadcast( self, channel, data ):

        def gotHomezones( homezones, self=self ):
            logger.info( "got SIM homezones: %s", homezones )
            self.homezones = homezones
            # debug code, if you have no homezones on your SIM. To test, use:
            # gsm.DebugInjectString("UNSOL","+CBM: 16,221,0,1,1\r\n347747555093\r\r\r\n")
            if HOMEZONE_DEBUG: self.homezones = [ ( "city", 347747, 555093, 1000 ), ( "home", 400000, 500000, 1000 ) ]
            self.checkInHomezones()

        if channel == 221: # home zone cell broadcast
            if len( data ) != 12:
                return
            self.x, self.y = int( data[:6] ), int( data[6:] )
            logger.info( "home zone cell broadcast detected: %s %s", self.x, self.y )
            if self.homezones is None: # never tried to read them
                logger.info( "trying to read home zones from SIM" )
                self.fso_sim.GetHomeZones( reply_handler=gotHomezones, error_handler=lambda error:None )
            else:
                self.checkInHomezones()

    def checkInHomezones( self ):
        status = ""
        for zname, zx, zy, zr in self.homezones:
            if self.checkInHomezone( self.x, self.y, zx, zy, zr ):
                status = zname
                break
        self.HomeZoneStatus( status )

    def checkInHomezone( self, x, y, zx, zy, zr ):
        logger.info( "matching whether %s %s is in ( %s, %s, %s )" % ( x, y, zx, zy, zr ) )
        dist = math.sqrt( math.pow( x-zx, 2 ) + math.pow( y-zy, 2 ) ) * 10
        maxdist = math.sqrt( zr ) * 10
        return dist < maxdist

    #
    # dbus org.freesmartphone.GSM.HZ
    #
    @dbus.service.method( DBUS_INTERFACE_HZ, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetHomeZoneStatus( self, dbus_ok, dbus_error ):
        dbus_ok( self.zone )

    @dbus.service.signal( DBUS_INTERFACE_HZ, "s" )
    def HomeZoneStatus( self, zone ):
        self.zone = zone
        logger.info( "home zone status now %s" % zone )

    @dbus.service.method( DBUS_INTERFACE_HZ, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetKnownHomeZones( self, dbus_ok, dbus_error ):

        def gotHomezones( homezones, self=self, dbus_ok=dbus_ok ):
            logger.info( "got SIM homezones: %s", homezones )
            self.homezones = homezones
            # debug code, if you have no homezones on your SIM. To test, use:
            # gsm.DebugInjectString("UNSOL","+CBM: 16,221,0,1,1\r\n347747555093\r\r\r\n")
            if HOMEZONE_DEBUG: self.homezones = [ ( "city", 347747, 555093, 1000 ), ( "home", 400000, 500000, 1000 ) ]
            dbus_ok( [ zone[0] for zone in self.homezones ] )

        self.fso_sim.GetHomeZones( reply_handler=gotHomezones, error_handler=lambda error:None )

    #
    # dbus org.freesmartphone.Network
    #
    @dbus.service.method( DBUS_INTERFACE_HZ, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetHomeZoneStatus( self, dbus_ok, dbus_error ):
        dbus_ok( self.zone )

    @dbus.service.signal( DBUS_INTERFACE_HZ, "s" )
    def HomeZoneStatus( self, zone ):
        self.zone = zone
        logger.info( "home zone status now %s" % zone )

    @dbus.service.method( DBUS_INTERFACE_HZ, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetKnownHomeZones( self, dbus_ok, dbus_error ):

        def gotHomezones( homezones, self=self, dbus_ok=dbus_ok ):
            logger.info( "got SIM homezones: %s", homezones )
            self.homezones = homezones
            # debug code, if you have no homezones on your SIM. To test, use:
            # gsm.DebugInjectString("UNSOL","+CBM: 16,221,0,1,1\r\n347747555093\r\r\r\n")
            if HOMEZONE_DEBUG: self.homezones = [ ( "city", 347747, 555093, 1000 ), ( "home", 400000, 500000, 1000 ) ]
            dbus_ok( [ zone[0] for zone in self.homezones ] )

        self.fso_sim.GetHomeZones( reply_handler=gotHomezones, error_handler=lambda error:None )

#=========================================================================#
def factory( prefix, controller ):
#=========================================================================#
    return [ Server( controller.bus ) ]

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
