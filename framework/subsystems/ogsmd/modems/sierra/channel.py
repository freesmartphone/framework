#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.sierra
Module: channel

This module contains a communication channel abstractions that
transport their data over a serial line.
"""

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class SierraChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        # usual stuff
        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=1') # report mobile equipment errors: in numerical format
        self.enqueue('+CRC=1') # cellular result codes: enable extended format
        self.enqueue('+CMGF=1') # message format: disable pdu mode, enable text mode
        #self.enqueue('+CSCS="8859-1"') # character set conversion: use 8859-1 (latin 1)
        self.enqueue('+CSDH=1') # show text mode parameters: show values

        # unsolicited
        self.enqueue('+CLIP=1') # calling line identification presentation enable
        self.enqueue('+COLP=1') # connected line identification presentation enable
        self.enqueue('+CCWA=1') # call waiting
        self.enqueue('+CRC=1') # cellular result codes: extended
        #self.enqueue('+CSNS=0') # single numbering scheme: voice
        #self.enqueue('+CTZU=1') # timezone update
        self.enqueue('+CTZR=1') # timezone reporting
        self.enqueue('+CREG=2') # registration information
        self.enqueue('+CGREG=2') # GPRS registration information
        self.enqueue('+CGEREP=2') # packet domain event reporting
        #self.enqueue('+CNMI=2,1,2,1,1') # buffer sms on SIM, report CB directly

