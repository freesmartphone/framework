#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.abstract
Module: channel
"""

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
import gobject

#=========================================================================#
class AbstractModemChannel( AtCommandChannel ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        self._commands = {}
        self._populateCommands()
        self._sendCommands( "init" )

        # FIXME add warm start handling (querying CFUN and CPIN status) here

    def modemStateAntennaOn( self ):
        """
        Called, when the modem signalizes the antenna being powered on.
        """
        self._sendCommands( "antenna" )

    def modemStateSimUnlocked( self ):
        """
        Called, when the modem signalizes the SIM being unlocked.
        """

        # don't hammer modem too early with the additional commands
        # FIXME it's actually modem specific whether we can send the command directly
        # after +CPIN: READY or not, so we should not have this here
        gobject.timeout_add_seconds( 2, self._sendCommands, "sim" )

    def modemStateSimReady( self ):
        """
        Called, when the modem signalizes the SIM data can be read.
        """
        pass
    #
    # internal API
    #

    def _sendCommands( self, state ):
        commands = self._commands[state]
        for command in commands:
            self.enqueue( command )

    def _populateCommands( self ):
        """
        Populate the command queues to be sent on modem state changes.
        """

        c = []
        # reset
        c.append( 'Z' )                 # soft reset
        c.append( 'E0V1' )              # echo off, verbose result on
        # error and result reporting reporting
        c.append( '+CMEE=1' )           # report mobile equipment errors: in numerical format
        c.append( '+CRC=1' )            # cellular result codes: enable extended format
        c.append( '+CSCS="8859-1"' )    # character set conversion: use 8859-1 (latin 1)
        c.append( '+CSDH=1' )           # show text mode parameters: show values
        c.append( '+CSNS=0' )           # single numbering scheme: voice
        # sms
        c.append( '+CMGF=1' )           # message format: disable pdu mode, enable text mode
        c.append( '+CSMS=1' )           # GSM Phase 2+ commands: enable
        # unsolicited
        c.append( '+CLIP=0' )           # calling line identification presentation: disable
        c.append( '+COLP=0' )           # connected line identification presentation: disable
        c.append( '+CCWA=0' )           # call waiting: disable
        self._commands["init"] = c

        c = []
        c.append( "+CNMI=2,1,2,1,1" )   # buffer sms on SIM, report CB directly

        self._commands["sim"] = c

        c = []
        self._commands["antenna"] = c
