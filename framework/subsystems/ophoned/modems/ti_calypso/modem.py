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

from ophoned.modems.abstract.modem import AbstractModem

from .channel import CallChannel, UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ophoned.gsm.decor import logged
from ophoned.gsm.channel import AtCommandChannel

#=========================================================================#
class TiCalypso( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # VC 1
        self._channels["CALL"] = CallChannel( self._bus, "ophoned.call" )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self._bus, "ophoned.unsolicited" )
        # VC 3
        self._channels["MISC"] = MiscChannel( self._bus, "ophoned.misc" )
        # VC 4
        # FIXME GPRS

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        if category == "CallMediator":
            return self._channels["CALL"]
        else:
            return self._channels["MISC"]

    def dataPort( self ):
        # FIXME this is already in VirtualChannel
        muxer = self._bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        return muxer.AllocChannel( "ophoned.gprs" )

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
