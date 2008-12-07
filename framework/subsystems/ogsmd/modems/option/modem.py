#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.option
Module: modem
"""

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.option"

import mediator

from ..abstract.modem import AbstractModem

from .channel import OptionChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class Option( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # The one and only serial line
        self._channels["UNSOL"] = OptionChannel( self.pathfactory, "/dev/ttyUSB2", modem=self )
        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        return self._channels["UNSOL"]

    def pathfactory( self, name ):
        return name

    def dataPort( self ):
        # FIXME remove duplication and just use pathfactory
        return "/dev/ttyUSB0"

    def dataOptions( self, category ):
        if category == "ppp":
            return [
                    '115200',
                    'nodetach',
                    'crtscts',
										"noipdefault",
										":10.0.0.1",
										"local",
                    'defaultroute',
                    'debug',
                    'hide-password',
                    'ipcp-accept-local',
                    'lcp-echo-failure', '10',
                    'lcp-echo-interval', '3',
                    'noauth',
                    #'demand',
                    'noipdefault',
                    'novj',
                    'novjccomp',
                    'persist',
                    ]
        else:
            return []

