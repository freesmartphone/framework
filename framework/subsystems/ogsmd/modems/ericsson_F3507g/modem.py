#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.ericsson_F3507g
Module: modem
"""

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.ericsson_F3507g"

import mediator

from ..abstract.modem import AbstractModem

from .channel import EricssonChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class EricssonF3507g( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # One line for unsolicited messages and modem communication
        # ttyACM1 will be used for data and ttyACM2 will be used for GPS data
        self._channels["SINGLE"] = EricssonChannel( self.pathfactory, "/dev/ttyACM0", modem=self )
        # configure channel
        self._channels["SINGLE"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        return self._channels["SINGLE"]

    def pathfactory( self, name ):
        return name

    def dataPort( self ):
        # FIXME remove duplication and just use pathfactory
        return "/dev/ttyACM1"

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
