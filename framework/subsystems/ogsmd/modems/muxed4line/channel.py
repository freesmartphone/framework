#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

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

        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=1') # report mobile equipment errors: in numerical format
        self.enqueue('+CRC=1') # cellular result codes: enable extended format
        self.enqueue('+CMGF=1') # message format: disable pdu mode, enable text mode
        self.enqueue('+CSCS="8859-1"') # character set conversion: use 8859-1 (latin 1)
        self.enqueue('+CSDH=1') # show text mode parameters: show values

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
        self.enqueue( "+CNMI=2,1,2,1,1" ) # buffer sms on SIM, report CB directly

        if "callback" in kwargs:
            self.callback = kwargs["callback"]
        else:
            self.callback = self

        self.prefixmap = { '+': 'plus',
                           '%': 'percent',
                           '@': 'at',
                           '/': 'slash',
                           '#': 'hash',
                           '_': 'underscore',
                           '*': 'star',
                           '&': 'ampersand',
                         }

        self.delegate = None

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

    @logged
    def handleUnsolicitedResponse( self, data ):
        if not data[0] in self.prefixmap:
            return False
        if not ':' in data:
            return False
        command, values = data.split( ':', 1 )

        if not self.delegate:
            return False

        methodname = "%s%s" % ( self.prefixmap[command[0]], command[1:] )

        try:
            method = getattr( self.delegate, methodname )
        except AttributeError:
            return False
        else:
            method( values.strip() )

        return True

    def setDelegate( self, object ):
        """
        Set a delegate object to which all unsolicited responses are delegated.
        """
        assert self.delegate is None, "delegate already set"
        self.delegate = object
