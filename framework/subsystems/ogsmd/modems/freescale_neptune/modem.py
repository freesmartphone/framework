#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: modem

Freescale Neptune modem class
"""

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import MiscChannel, UnsolicitedResponseChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class FreescaleNeptune( AbstractModem ):
#=========================================================================#
    """
    Support for the Freescale Neptune embedded modem as found in the Motorola EZX
    Linux Smartphones E680, A780, A910, A1200, A1600, ROKR E2, ROKR E6, and more.

    We have a hardwired multiplexing mode configuration as follows:
    ----------------------------------------------------------------
       DLC     Description          Cmd     Device      Mode
    ----------------------------------------------------------------
        0   Control Channel         -          -
        1   Voice Call & Network    MM      /dev/mux0   Modem
        2   SMS                     MO      /dev/mux1   Phonebook
        3   SMS MT                          /dev/mux2   Phonebook
        4   Phonebook               SIM     /dev/mux3   Phonebook
        5   Misc                            /dev/mux4   Phonebook
        6   CSD / Fax             /dev/mux5 /dev/mux8   Modem
        7   GPRS 1                /dev/mux6 /dev/mux9   Modem
        8   GPRS 2                /dev/mux7 /dev/mux10  Modem
        9   Logger CMD            /dev/mux11
        10  Logger Data           /dev/mux12
        11  Test CMD              /dev/mux13
        12  AGPS                  /dev/mux14
        13  NetMonitor            /dev/mux15
    ----------------------------------------------------------------

    ...
    """

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        self._channels[ "UNSOL" ] = UnsolicitedResponseChannel( self.pathfactory, "/dev/mux0" ) # might also be callchannel, if /dev/mux2 does not want to
        self._channels[ "CALL" ] = MiscChannel( self.pathfactory, "/dev/mux2" )
        #self._channels[ "MISC" ] = MiscChannel( self.pathfactory, "/dev/mux4" ) # needs to parse unsolicited
        self._channels[ "MISC" ] = MiscChannel( self.pathfactory, "/dev/mux6" )

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def channel( self, category ):
        if category == "CallMediator":
            return self._channels["CALL"]
        elif category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
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
