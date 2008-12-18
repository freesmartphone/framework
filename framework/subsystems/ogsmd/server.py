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
__version__ = "0.2.0"

from framework import resource
from framework.patterns import tasklet
from gsm import const

import dbus
import dbus.service
from dbus import DBusException

import math
import sys, os
import types

import logging
logger = logging.getLogger( MODULE_NAME )

from device import DBUS_INTERFACE_DEVICE, \
                   DBUS_OBJECT_PATH_DEVICE, \
                   DBUS_BUS_NAME_DEVICE, \
                   DBUS_INTERFACE_SIM, \
                   DBUS_INTERFACE_NETWORK, \
                   DBUS_INTERFACE_CB

DBUS_INTERFACE_DATA = "org.freesmartphone.GSM.Data"
DBUS_INTERFACE_HZ = "org.freesmartphone.GSM.HZ"
DBUS_INTERFACE_PHONE = "org.freesmartphone.GSM.Phone"
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
        self._autoRegister = False
        self._service = "unknown"
        self.pin = None

    def setupSignals( self ):
        device = self.bus.get_object( DBUS_BUS_NAME_DEVICE, DBUS_OBJECT_PATH_DEVICE )
        self.fso_cb = dbus.Interface( device, DBUS_INTERFACE_CB )
        self.fso_cb.connect_to_signal( "IncomingCellBroadcast", self.onIncomingCellBroadcast )
        self.fso_sim = dbus.Interface( device, DBUS_INTERFACE_SIM )
        self.fso_network = dbus.Interface( device, DBUS_INTERFACE_NETWORK )
        self.fso_network.connect_to_signal( "Status", self.onIncomingGsmNetworkStatus )
        self.fso_device = dbus.Interface( device, DBUS_INTERFACE_DEVICE )

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

    def onIncomingGsmNetworkStatus( self, status ):
        reg = status["registration"]
        if reg in "home roaming".split():
            self._updateServiceStatus( "online" )
        else:
            self._updateServiceStatus( "offline" )
        if reg in "unregistered denied".split() and self._autoRegister:
            self.Register( self.pin, lambda:None, lambda Foo:None )

    def _updateServiceStatus( self, status ):
        if self._service != status:
            self._service = status
            self.ServiceStatus( status )

    #
    # dbus org.freesmartphone.GSM.Data
    #
    @dbus.service.method( DBUS_INTERFACE_DATA, "ss", "a{sv}" )
    def GetNetworkInfo( self, mcc, mnc ):
        return const.NETWORKS.get( ( mcc, mnc ), {} )

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
    # dbus org.freesmartphone.GSM.Phone
    #
    @dbus.service.method( DBUS_INTERFACE_PHONE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StartAutoRegister( self, pin, dbus_ok, dbus_error ):
        self.pin = pin
        self._autoRegister = True
        dbus_ok()

        self.fso_network.GetStatus( reply_handler=self.onIncomingGsmNetworkStatus, error_handler=lambda Foo:None )

    @dbus.service.method( DBUS_INTERFACE_PHONE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopAutoRegister( self, dbus_ok, dbus_error ):
        self._autoRegister = False
        dbus_ok()

    @dbus.service.method( DBUS_INTERFACE_PHONE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Register( self, pin, dbus_ok, dbus_error ):

        @tasklet.tasklet
        def worker( self, pin ):
            try:
                yield tasklet.WaitDBus( self.fso_device.SetAntennaPower, True )
            except dbus.DBusException, e: # may be locked
                if e.get_dbus_name() != "org.freesmartphone.GSM.SIM.AuthFailed":
                    raise
                else:
                    yield tasklet.WaitDBus( self.fso_sim.SendAuthCode, pin )

            yield tasklet.WaitDBus( self.fso_network.Register )
        worker( self, pin ).start_dbus( dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_PHONE, "s" )
    def ServiceStatus( self, service ):
       logger.info( "service status now %s" % service )

#=========================================================================#
def factory( prefix, controller ):
#=========================================================================#
    return [ Server( controller.bus ) ]

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
