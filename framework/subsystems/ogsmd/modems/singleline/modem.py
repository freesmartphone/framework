#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.singleline
Module: modem
"""

import mediator

from ..abstract.modem import AbstractModem

from .channel import SingleLineChannel
from .unsolicited import UnsolicitedResponseDelegate

#=========================================================================#
class SingleLine( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # The one and only serial line
        self._channels["SINGLE"] = SingleLineChannel( self.portfactory, "ogsmd", modem=self )
        # configure channels
        self._channels["SINGLE"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
            # we do not care about a category here, we only have one channel
            return self._channels["SINGLE"]

    def portfactory( self, name ):
        # FIXME read from configuration
        return "/dev/ttySAC0"
