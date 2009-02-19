#!/usr/bin/env python
"""
The Open GSM Daemon -- Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.cinterion_mc75
Module: channel
"""

from ogsmd.modems.abstract.channel import AbstractModemChannel
from ogsmd.gsm.callback import SimpleCallback

import itertools, select

import logging
logger = logging.getLogger( "ogsmd.modems.cinterion_mc75.channel" )

#=========================================================================#
class CinterionModemChannel( AbstractModemChannel ):
#=========================================================================#
    pass

#=========================================================================#
class MiscChannel( CinterionModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60
        CinterionModemChannel.__init__( self, *args, **kwargs )
        self.callback = None

    def setIntermediateResponseCallback( self, callback ):
        assert self.callback is None, "callback already set"
        self.callback = callback

    def handleUnsolicitedResponse( self, response ):
        if self.callback is not None:
            self.callback( response )
        else:
            print "CALLCHANNEL: UNHANDLED INTERMEDIATE: ", response

#=========================================================================#
class UnsolicitedResponseChannel( CinterionModemChannel ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        CinterionModemChannel.__init__( self, *args, **kwargs )

    def _populateCommands( self ):
        CinterionModemChannel._populateCommands( self )

        c = self._commands["init"]
        # enable unsolicited codes

        c.append( "+CLIP=1" ) # calling line identification presentation enable
        c.append( "+COLP=1" ) # connected line identification presentation enable
        c.append( "+CCWA=1" ) # call waiting: send unsol. code
        c.append( "+CSSN=1,1") # supplementary service notifications: send unsol. code
        c.append( "+CRC=1" ) # cellular result codes: extended
        c.append( "+CSNS=0" ) # single numbering scheme: voice
        c.append( "+CTZU=1" ) # timezone update
        c.append( "+CTZR=1" ) # timezone reporting
        c.append( "+CREG=2" ) # registration information (TODO not all modems support that)
