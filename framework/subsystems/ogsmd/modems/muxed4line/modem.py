#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.muxed4line
Module: modem
"""

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import CallChannel, UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class Muxed4Line( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # VC 1
        self._channels["CALL"] = CallChannel( self.pathfactory, "ogsmd.call" )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self.pathfactory, "ogsmd.unsolicited" )
        # VC 3
        self._channels["MISC"] = MiscChannel( self.pathfactory, "ogsmd.misc" )
        # VC 4
        # GPRS

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        if category == "CallMediator":
            return self._channels["CALL"]
        elif category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self ):
        """Allocate a new channel from the MUXer."""
        muxer = self._bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        return str( muxer.AllocChannel( self.name ) )
