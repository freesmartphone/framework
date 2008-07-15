#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.singeline
Module: channel
"""

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

#=========================================================================#
class SingleLineChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60

        # reset
        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on

        # error and result reporting reporting
        self.enqueue('+CMEE=1') # report mobile equipment errors: in numerical format
        self.enqueue('+CRC=1') # cellular result codes: enable extended format
        self.enqueue('+CSCS="8859-1"') # character set conversion: use 8859-1 (latin 1)
        self.enqueue('+CSDH=1') # show text mode parameters: show values

        # sms
        self.enqueue('+CMGF=1') # message format: disable pdu mode, enable text mode
        self.enqueue('+CSMS=1') # GSM Phase 2+ commands: enable

        # unsolicited
        self.enqueue('+CLIP=1') # calling line identification presentation enable
        self.enqueue('+COLP=1') # connected line identification presentation enable
        self.enqueue('+CCWA=1') # call waiting
        self.enqueue('+CRC=1') # cellular result codes: extended
        self.enqueue('+CSNS=0') # single numbering scheme: voice
        self.enqueue('+CTZU=1') # timezone update
        self.enqueue('+CTZR=1') # timezone reporting
        self.enqueue('+CREG=2') # registration information (TODO not all modems support that)

        # this will error until SIM authenticated
        self.enqueue('+CNMI=2,1,2,1,1') # buffer sms on SIM, report CB directly

    @logged
    def open( self, path="/dev/ttySAC0" ):
        AtCommandChannel.open( self, path )
