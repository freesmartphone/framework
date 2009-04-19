#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: modem

"""

__version__ = "0.9.9.10"
MODULE_NAME = "ogsmd.modems.ti_calypso"

DEVICE_CALYPSO_PATH             = "/dev/ttySAC0"
SYSFS_CALYPSO_POWER_PATH        = "/sys/bus/platform/devices/neo1973-pm-gsm.0/power_on"
SYSFS_CALYPSO_RESET_PATH        = "/sys/bus/platform/devices/neo1973-pm-gsm.0/reset"
SYSFS_CALYPSO_FLOW_CONTROL_PATH = "/sys/bus/platform/devices/neo1973-pm-gsm.0/flowcontrolled"

import mediator

from framework.config import config
from framework.patterns.utilities import killall

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import CallChannel, UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.helpers import writeToFile


from dbus import Interface
from time import sleep

import serial

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class TiCalypso( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        self._channelmap = { "ogsmd.call":1, "ogsmd.unsolicited":2, "ogsmd.misc":3, "ogsmd.gprs":4 }

        # VC 1
        self._channels["CALL"] = CallChannel( self.pathfactory, "ogsmd.call", modem=self )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self.pathfactory, "ogsmd.unsolicited", modem=self )
        # VC 3
        self._channels["MISC"] = MiscChannel( self.pathfactory, "ogsmd.misc", modem=self )
        # VC 4
        # FIXME pre-allocate GPRS channel for pppd?

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

        # configure behaviour using special commands
        self._data["cancel-outgoing-call"] = "%CHLD=I"

        # muxer mode
        self._muxercommand = config.getValue( "ogsmd", "ti_calypso_muxer", "gsm0710muxd" )

        # muxer object
        self._muxeriface = None

    def _modemOn( self ):
        """
        Lowlevel initialize this modem.
        """
        logger.debug( "reset-cycling modem" )
        writeToFile( SYSFS_CALYPSO_POWER_PATH, "0\n" )
        sleep( 1 )
        writeToFile( SYSFS_CALYPSO_RESET_PATH, "0\n" )
        sleep( 1 )
        writeToFile( SYSFS_CALYPSO_POWER_PATH, "1\n" )
        sleep( 1 )
        writeToFile( SYSFS_CALYPSO_RESET_PATH, "1\n" )
        sleep( 1 )
        writeToFile( SYSFS_CALYPSO_RESET_PATH, "0\n" )
        sleep( 1 )
        logger.debug( "reset cycle complete" )

        device = serial.Serial()
        device.port = DEVICE_CALYPSO_PATH
        device.baudrate = 115200
        device.rtscts = True
        device.xonxoff = False
        device.bytesize = serial.EIGHTBITS
        device.parity = serial.PARITY_NONE
        device.stopbits = serial.STOPBITS_ONE
        device.timeout = 1
        logger.debug( "opening port now" )
        device.open()
        device.write( "\0xf9\0xf9" )
        device.flush()
        sleep( 0.2 )
        device.write( "\0x7E\0x03\0xEF\0xC3\0x01\0x70\0x7E" )
        device.flush()
        sleep( 0.2 )
        device.write( "\r\nAT\r\n" )
        device.flush()
        result = device.read( 64 )
        logger.debug( "got %s", repr(result) )
        ok = False
        for retries in xrange( 5 ):
            logger.debug( "port open, sending ATE0" )
            device.write( "ATE0\r\n" )
            device.flush()
            result = device.read( 64 )
            logger.debug( "got %s", repr(result) )
            if "OK" in result:
                ok = True
                break
        device.close()
        return ok

    def _modemOff( self ):
        writeToFile( SYSFS_CALYPSO_POWER_PATH, "0\n" )

    def close( self ): # SYNC
        """
        Close modem.

        Overriden for internal purposes.
        """
        # call default implementation (closing all channels)
        AbstractModem.close( self )
        killall( self._muxercommand )
        self._modemOff()

    def channel( self, category ):
        """
        Return proper channel.

        Overridden for internal purposes.
        """
        if category == "CallMediator":
            return self._channels["CALL"]
        elif category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self, name ):
        """
        Allocate a new channel from the MUXer.

        Overridden for internal purposes.
        """
        logger.info( "Requesting new channel from '%s'", self._muxercommand )

        if self._muxercommand == "gsm0710muxd":
            if self._muxeriface is None:
                muxer = self._bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
                self._muxeriface = Interface( muxer, "org.freesmartphone.GSM.MUX" )
            return str( self._muxeriface.AllocChannel( name ) )

        elif self._muxercommand == "fso-abyss":
            if self._muxeriface is None:
                muxer = self._bus.get_object( "org.freesmartphone.omuxerd", "/org/freesmartphone/GSM/Muxer" )
                self._muxeriface = Interface( muxer, "org.freesmartphone.GSM.MUX" )
                # power on modem
                if not self._modemOn():
                    self._muxeriface = None
                    return "" # FIXME: emit error?
                if not self._muxeriface.HasAutoSession():
                    # abyss needs an open session before we can allocate channels
                    self._muxeriface.OpenSession( True, 98, DEVICE_CALYPSO_PATH, 115200 )
            pts, vc = self._muxeriface.AllocChannel( name, self._channelmap[name] )
            return str(pts)

    def dataPort( self ):
        return self.pathfactory( "ogsmd.gprs" )

    def prepareForSuspend( self, ok_callback, error_callback ):
        """overridden for internal purposes"""

        # FIXME still no error handling here

        def post_ok( ok_callback=ok_callback ):
            writeToFile( SYSFS_CALYPSO_FLOW_CONTROL_PATH, "1" )
            ok_callback()

        AbstractModem.prepareForSuspend( self, post_ok, error_callback )

    def recoverFromSuspend( self, ok_callback, error_callback ):
        writeToFile( SYSFS_CALYPSO_FLOW_CONTROL_PATH, "0" )
        AbstractModem.recoverFromSuspend( self, ok_callback, error_callback )
