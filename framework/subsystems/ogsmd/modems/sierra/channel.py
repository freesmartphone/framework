#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.sierra
Module: channel
"""

from ogsmd.gsm.decor import logged
from ogsmd.modems.abstract.channel import AbstractModemChannel

#=========================================================================#
class SierraChannel( AbstractModemChannel ):
#=========================================================================#

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
        # c.append( '+CSCS="8859-1"' )    # character set conversion: use 8859-1 (latin 1)
        c.append( '+CSDH=1' )           # show text mode parameters: show values
        c.append( '+CSNS=0' )           # single numbering scheme: voice
        # sms
        c.append( '+CMGF=0' )           # message format: enable pdu mode, disable text mode
        c.append( '+CSMS=1' )           # GSM Phase 2+ commands: enable
        # unsolicited
        c.append( '+CLIP=1' )           # calling line identification presentation: disable
        c.append( '+COLP=1' )           # connected line identification presentation: disable
        c.append( '+CCWA=1' )           # call waiting: disable
        c.append( '+CTZR=1' )           # timezone reporting: enable
        c.append( '+CREG=2' )           # registration information: enable
        c.append( '+CGREG=2' )          # GPRS registration information: enable
        c.append( '+CGEREP=2')          # Packet domain event reporting: enable
        self._commands["init"] = c

        c = []
        # c.append( "+CNMI=2,1,2,1,1" )   # buffer sms on SIM, report CB directly

        self._commands["sim"] = c

        c = []
        self._commands["antenna"] = c
