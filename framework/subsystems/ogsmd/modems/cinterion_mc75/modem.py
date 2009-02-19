#!/usr/bin/env python
"""
The Open GSM Daemon -- Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.cinterion_mc75
Module: modem
"""

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.cinterion_mc75"

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

#=========================================================================#
class CinterionMc75( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # VC 1
        self._channels["MISC"] = MiscChannel( self.pathfactory, "ogsmd.misc", modem=self )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self.pathfactory, "ogsmd.unsolicited", modem=self )
        # VC 3
        # GPRS

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        if category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self, name ):
        """
        Allocate a new channel from the MUXer.

        Overridden for internal purposes.
        """
        muxer = self._bus.get_object( "org.freesmartphone.omuxerd", "/org/freesmartphone/GSM/Muxer" )
        port, channel = muxer.AllocChannel( name, 0, dbus_interface="org.freesmartphone.GSM.MUX" )
        return str( port )

    def dataPort( self ):
        return self.pathfactory( "ogsmd.gprs" )
