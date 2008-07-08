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

    @logged
    def _hookLowLevelInit( self ):
        """
        Low level initialization of channel.

        This is actually an ugly hack which is unfortunately
        necessary since the TI multiplexer obviously has problems
        wrt. to initialization (swallowing first bunch of commands now and then...)
        To work around this, we send '\x1a\r\n' until we actually get an
        'OK' from the modem. We try this for 5 times, then we reopen
        the serial line. If after 10 times we still have no response,
        we assume that the modem is broken and fail.
        """

        return True

        for i in itertools.count():
            print "(modem init... try #%d)" % ( i+1 )
            select.select( [], [self.serial.fd], [], 0.5 )
            self.serial.write( "\x1a\r\n" )
            r, w, x = select.select( [self.serial.fd], [], [], 0.5 )
            if r:
                try:
                    buf = self.serial.inWaiting()
                except:
                    self.serial.close()
                    path = self.pathfactory( self.name )
                    if not path:
                        return False
                    self.serial.port = str( path )
                    self.serial.open()
                    buf = self.serial.inWaiting()
                ok = self.serial.read(buf).strip()
                print "read:", repr(ok)
                if "OK" in ok or "AT" in ok:
                    break
            print "(modem not responding)"
            if i == 5:
                print "(reopening modem)"
                self.serial.close()
                path = self.pathfactory( self.name )
                if not path:
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                print "(giving up)"
                self.serial.close()
                return False
        print "(modem responding)"
        self.serial.flushInput()

        return True

#=========================================================================#
class MiscChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

