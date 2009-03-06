#!/usr/bin/env python
"""
The Open GSM Daemon -- Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.cinterion_mc75
Module: modem
"""

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.cinterion_mc75"

MODEM_DEVICE_PATH             = "/dev/ttySAC1"
MODEM_SYSFS_POWER_PATH        = "/sys/bus/platform/devices/om-3d7k.0/gsm_power"

import mediator

from ogsmd.modems.abstract.modem import AbstractModem
from ogsmd.helpers import writeToFile

from .channel import UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from dbus import Interface

from time import sleep

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class CinterionMc75( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        self._channelmap = { "ogsmd.misc":1, "ogsmd.unsolicited":2 }

        # VC 1
        self._channels["MISC"] = MiscChannel( self.pathfactory, "ogsmd.misc", modem=self )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self.pathfactory, "ogsmd.unsolicited", modem=self )
        # VC 3
        # GPRS

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

        # muxer object
        self._muxeriface = None

    def _modemOn( self ):
        """
        Lowlevel initialize this modem.
        """
        logger.debug( "reset-cycling modem" )
        writeToFile( MODEM_SYSFS_POWER_PATH, "0\n" )
        sleep( 1 )
        writeToFile( MODEM_SYSFS_POWER_PATH, "1\n" )
        sleep( 1 )
        logger.debug( "reset cycle complete" )
        sleep( 2 )
        # FIXME open device node and listen for \r\n^SYSSTART\r\n
        return True

    def _modemOff( self ):
        """
        Lowlevel deinitialize this modem.
        """
        writeToFile( MODEM_SYSFS_POWER_PATH, "0\n" )

    def channel( self, category ):
        """
        Return proper outgoing channel for command category.
        """
        if category in ( "UnsolicitedMediator", "NetworkMediator" ):
            return self._channels["UNSOL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self, name ):
        """
        Allocate a new channel from the MUXer.

        Overridden for internal purposes.
        """
        logger.info( "Requesting new channel from multiplexer" )

        if self._muxeriface is None:
            muxer = self._bus.get_object( "org.freesmartphone.omuxerd", "/org/freesmartphone/GSM/Muxer" )
            self._muxeriface = Interface( muxer, "org.freesmartphone.GSM.MUX" )
            # power on modem
            if not self._modemOn():
                self._muxeriface = None
                return "" # FIXME: emit error?
            if not self._muxeriface.HasAutoSession():
                # abyss needs an open session before we can allocate channels
                self._muxeriface.OpenSession( True, 98, MODEM_DEVICE_PATH, 115200 )
        pts, vc = self._muxeriface.AllocChannel( name, self._channelmap[name] )
        return str(pts)

    def dataPort( self ):
        return self.pathfactory( "ogsmd.gprs" )
