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

from .channel import MiscChannel, UnsolicitedResponseChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class MotorolaEzx( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        self._channels[ "UNSOL" ] = UnsolicitedResponseChannel( self.pathfactory, "/dev/mux0" )
        self._channels[ "CALL" ] = MiscChannel( self.pathfactory, "/dev/mux1" )
        self._channels[ "MISC" ] = MiscChannel( self.pathfactory, "/dev/mux2" )
        # self._channels[ "UNSOL2" ] = MiscChannel( self.pathfactory, "/dev/mux4" )

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
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
