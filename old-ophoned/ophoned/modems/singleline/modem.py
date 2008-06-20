#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned.modems.singleline
Module: modem
"""

import mediator

from ..abstract.modem import AbstractModem

from .channel import SingleLineChannel
from .unsolicited import UnsolicitedResponseDelegate

from ophoned.gsm.decor import logged
from ophoned.gsm.channel import AtCommandChannel

#=========================================================================#
class SingleLine( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # The one and only serial line
        self._channels["SINGLE"] = SingleLineChannel( self._bus, "ophoned" )
        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
            return self._channels["SINGLE"]
