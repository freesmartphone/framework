#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: modem

Freescale Neptune modem class
"""

__version__ = "0.3.1"
MODULE_NAME = "ogsmd.modems.freescale_neptune"

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import CallAndNetworkChannel, MiscChannel, SmsChannel, SimChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

import types

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
        3   SMS                     MT      /dev/mux2   Phonebook
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

        # /dev/mux0
        self._channels[ "CallAndNetwork" ] = CallAndNetworkChannel( self.pathfactory, "/dev/mux0", modem=self )
        # /dev/mux2
        self._channels[ "Sms" ] = SmsChannel( self.pathfactory, "/dev/mux2", modem=self )
        # /dev/mux4
        self._channels[ "Sim" ] = SimChannel( self.pathfactory, "/dev/mux4", modem=self )
        # /dev/mux6
        self._channels[ "Misc" ] = MiscChannel( self.pathfactory, "/dev/mux6", modem=self )

        # configure channels
        self._channels["CallAndNetwork"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )
        self._channels["Sms"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )
        self._channels["Sim"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def numberToPhonebookTuple( self, nstring ):
        """
        Modem violating GSM 07.07 here. It always includes the '+' for international numbers,
        although this should only be encoded via ntype = '145'.
        """
        if type( nstring ) != types.StringType():
            # even though we set +CSCS="UCS2" (modem charset), the name is always encoded in text format, not PDU.
            nstring = nstring.encode( "iso-8859-1" )

        if nstring[0] == '+':
            return nstring, 145
        else:
            return nstring, 129

    def channel( self, category ):
        if category == "CallMediator":
            return self._channels["CallAndNetwork"]
        elif category == "UnsolicitedMediator":
            return self._channels["Sms"]
        elif category == "SimMediator":
            return self._channels["Sim"]
        else:
            return self._channels["Misc"]

    def pathfactory( self, name ):
        return name
