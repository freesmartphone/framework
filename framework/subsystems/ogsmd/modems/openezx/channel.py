#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.openezx
Module: channel

Motorola EZX specific modem channels
"""

import time
import itertools
import select

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.gsm.callback import SimpleCallback

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

#=========================================================================#
class UnsolicitedResponseChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )
