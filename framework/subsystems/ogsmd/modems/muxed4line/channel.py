#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: channel

This module contains communication channel abstractions that
transport their data over a (virtual) serial line.
"""

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.gsm.callback import SimpleCallback

#=========================================================================#
class GenericModemChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        # reset
        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on

        # result and error reporting
        self.enqueue('+CMEE=1') # report mobile equipment errors: in numerical format
        self.enqueue('+CRC=1') # cellular result codes: enable extended format
        self.enqueue('+CSCS="8859-1"') # character set conversion: use 8859-1 (latin 1)
        self.enqueue('+CSDH=1') # show text mode parameters: show values

        # sms
        self.enqueue('+CMGF=1') # message format: disable pdu mode, enable text mode
        self.enqueue('+CSMS=1') # sms gsm phase 2+ extensions: enable


#=========================================================================#
class CallChannel( GenericModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60
        GenericModemChannel.__init__( self, *args, **kwargs )
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
class MiscChannel( GenericModemChannel ):
#=========================================================================#
    pass

#=========================================================================#
class UnsolicitedResponseChannel( GenericModemChannel ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        GenericModemChannel.__init__( self, *args, **kwargs )

        self.enqueue( "+CLIP=1" ) # calling line identification presentation enable
        self.enqueue( "+COLP=1" ) # connected line identification presentation enable
        self.enqueue( "+CCWA=1" ) # call waiting: send unsol. code
        self.enqueue( "+CSSN=1,1") # supplementary service notifications: send unsol. code
        self.enqueue( "+CRC=1" ) # cellular result codes: extended
        self.enqueue( "+CSNS=0" ) # single numbering scheme: voice
        self.enqueue( "+CTZU=1" ) # timezone update
        self.enqueue( "+CTZR=1" ) # timezone reporting
        self.enqueue( "+CREG=2" ) # registration information (TODO not all modems support that)

        # NOTE: This fails until CFUN=4 or CFUN=1 and SIM Auth is given
        self.enqueue( "+CNMI=2,1,2,1,1" ) # buffer SMS on SIM, report new SMS after storing, report CB directly

    @logged
    def suspend( self, ok_callback, error_callback ):
        self.enqueue( "+CTZU=0;+CTZR=0;+CREG=0;+CNMI=2,1,0,0,0",
                      SimpleCallback( ok_callback, self ),
                      SimpleCallback( error_callback, self ) )

    @logged
    def resume( self, ok_callback, error_callback ):
        self.enqueue( "+CTZU=1;+CTZR=1;+CREG=2;+CNMI=2,1,2,1,1",
                      SimpleCallback( ok_callback, self ),
                      SimpleCallback( error_callback, self ) )
