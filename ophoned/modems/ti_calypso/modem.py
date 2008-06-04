#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned.modems.muxed4line
Module: modem

DBus Exception Classes for org.freesmartphone.GSM*
"""

import mediator

from ..muxed4line.modem import Muxed4Line

from .channel import CallChannel, UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ophoned.gsm.decor import logged
from ophoned.gsm.channel import AtCommandChannel

#=========================================================================#
class TiCalypso( Muxed4Line ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        Muxed4Line.__init__( self, *args, **kwargs )
