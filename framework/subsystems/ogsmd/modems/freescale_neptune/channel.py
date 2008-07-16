#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: channel

Freescale Neptune specific modem channels
"""

import time
import itertools
import select

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.gsm.callback import SimpleCallback
from ogsmd.gsm.parser import ThrowStuffAwayParser

#=========================================================================#
class EzxMuxChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        self.enqueue( "Z" ) # soft reset
        self.enqueue( "E0V1" ) # echo off, verbose result on
        self.enqueue( "+CMEE=1" ) # report mobile equipment errors: in numerical format
        self.enqueue( "+CRC=1" ) # cellular result codes: enable extended format
        self.enqueue( "+CMGF=1" ) # message format: disable pdu mode, enable text mode
        self.enqueue( '+CSCS="8859-1" ') # character set conversion: use 8859-1 (latin 1)
        self.enqueue( "+CSDH=1" ) # show text mode parameters: show values

        self.enqueue( '+CPBS="SM"' ) # choose SIM phonebook

#=========================================================================#
class MiscChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

        # FIXME we can't do this, since it is modem-wide (not VC-wide)
        #self.enqueue( "+CMER=0,0,0,0,0" ) # unsolicited event reporting: none

    def installParser( self ):
        trash = [ "+CIEV:" ]
        self.parser = ThrowStuffAwayParser( trash, self._handleResponseToRequest, self._handleUnsolicitedResponse )

#=========================================================================#
class UnsolicitedResponseChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )
