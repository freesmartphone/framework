#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.openezx
Module: modem

Motorola EZX modem class
"""

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class MotorolaEzx( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        for i in xrange( 1 ): # two channels for now
            self._channels[ "MUX%d" % i ] = MiscChannel( self.pathfactory, "/dev/mux%d" % i )

    def channel( self, category ):
        return self._channels["MUX0"]

        if category == "CallMediator":
            return self._channels["CALL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self, name ):
        return name

    def dataOptions( self, category ):
        if category == "ppp":
            return [
                    '115200',
                    'nodetach',
                    'crtscts',
                    'defaultroute',
                    'debug',
                    'hide-password',
                    'holdoff', '3',
                    'ipcp-accept-local',
                    'ktune',
                    'lcp-echo-failure', '8',
                    'lcp-echo-interval', '3',
                    'ipcp-max-configure', '32',
                    'lock',
                    'noauth',
                    #'demand',
                    'noipdefault',
                    'novj',
                    'novjccomp',
                    #'persist',
                    'proxyarp',
                    'replacedefaultroute',
                    'usepeerdns' ]
        else:
            return []
