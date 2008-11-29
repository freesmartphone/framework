#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.sierra
Module: modem
"""

import mediator

from ..abstract.modem import AbstractModem

from .channel import SierraChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class Sierra( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # The one and only serial line
        self._channels["SINGLE"] = SierraChannel( self.pathfactory, "/dev/ttyUSB0", modem=self )
        # configure channels
        self._channels["SINGLE"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        return self._channels["SINGLE"]

    def pathfactory( self, name ):
        return name

