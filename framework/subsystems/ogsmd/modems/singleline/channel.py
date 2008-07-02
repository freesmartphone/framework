#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.singeline
Module: channel

This module contains a communication channel abstractions that
transport their data over a serial line.
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

        # usual stuff
        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=1') # report mobile equipment errors: in numerical format
        self.enqueue('+CRC=1') # cellular result codes: enable extended format
        self.enqueue('+CMGF=1') # message format: disable pdu mode, enable text mode
        self.enqueue('+CSCS="8859-1"') # character set conversion: use 8859-1 (latin 1)
        self.enqueue('+CSDH=1') # show text mode parameters: show values

        # unsolicited
        self.enqueue('+CLIP=1') # calling line identification presentation enable
        self.enqueue('+COLP=1') # connected line identification presentation enable
        self.enqueue('+CCWA=1') # call waiting
        self.enqueue('+CRC=1') # cellular result codes: extended
        self.enqueue('+CSNS=0') # single numbering scheme: voice
        self.enqueue('+CTZU=1') # timezone update
        self.enqueue('+CTZR=1') # timezone reporting
        self.enqueue('+CREG=2') # registration information (TODO not all modems support that)
        self.enqueue('+CNMI=2,1,2,1,1') # buffer sms on SIM, report CB directly

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
    def open( self, path="/dev/ttySAC0" ):
        AtCommandChannel.open( self, path )

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

