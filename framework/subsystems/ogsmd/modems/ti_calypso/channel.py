#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: channel

TI Calypso specific modem channels
"""

import time
import itertools
import select

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.gsm.callback import SimpleCallback

#=========================================================================#
class CalypsoModemChannel( AtCommandChannel ):
#=========================================================================#
    modem_communication_timestamp = 1

    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )

        # reset
        self.enqueue( "Z" ) # soft reset
        self.enqueue( "E0V1" ) # echo off, verbose result on

        # result and error reporting
        self.enqueue( "+CMEE=1" ) # report mobile equipment errors: in numerical format
        self.enqueue( "+CRC=1" ) # cellular result codes: enable extended format
        self.enqueue( '+CSCS="8859-1" ') # character set conversion: use 8859-1 (latin 1)
        self.enqueue( "+CSDH=1" ) # show text mode parameters: show values

        # sms
        self.enqueue( "+CMGF=1" ) # message format: disable pdu mode, enable text mode
        self.enqueue( "+CSMS=1" ) # gsm phase 2+ extensions: enable


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
                    path = self.pathfactory()
                    if not path: # path is None or ""
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
                path = self.pathfactory()
                if not path: # path is None or ""
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                print "(giving up)"
                self.serial.close()
                return False
        print "(modem responding)"
        self.serial.flushInput()

        # reset global modem communication timestamp
        if CalypsoModemChannel.modem_communication_timestamp:
            CalypsoModemChannel.modem_communication_timestamp = time.time()

        return True

    def _hookPreReading( self ):
        if CalypsoModemChannel.modem_communication_timestamp:
            CalypsoModemChannel.modem_communication_timestamp = time.time()

    def _hookPostReading( self ):
        pass

    def _hookPreSending( self ):
        if CalypsoModemChannel.modem_communication_timestamp:
            current_time = time.time()
            if current_time - CalypsoModemChannel.modem_communication_timestamp > 7:
                print "(%s: last communication with modem was %d seconds ago. Sending EOF to wakeup)" % ( repr(self), int(current_time - CalypsoModemChannel.modem_communication_timestamp) )
                self.serial.write( "\x1a" )
                time.sleep( 0.2 )
            CalypsoModemChannel.modem_communication_timestamp = current_time

    def _hookPostSending( self ):
        if CalypsoModemChannel.modem_communication_timestamp:
            CalypsoModemChannel.modem_communication_timestamp = time.time()

#=========================================================================#
class CallChannel( CalypsoModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60
        CalypsoModemChannel.__init__( self, *args, **kwargs )
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
class MiscChannel( CalypsoModemChannel ):
#=========================================================================#
    pass

#=========================================================================#
class UnsolicitedResponseChannel( CalypsoModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        CalypsoModemChannel.__init__( self, *args, **kwargs )

        self.enqueue( "+CLIP=1" ) # calling line identification presentation enable
        self.enqueue( "+COLP=1" ) # connected line identification presentation enable
        self.enqueue( "+CCWA=1" ) # call waiting: send unsol. code
        self.enqueue( "+CSSN=1,1") # supplementary service notifications: send unsol. code
        self.enqueue( "+CRC=1" ) # cellular result codes: extended
        self.enqueue( "+CSNS=0" ) # single numbering scheme: voice
        self.enqueue( "+CTZU=1" ) # timezone update: send unsol. code
        self.enqueue( "+CTZR=1" ) # timezone reporting: send unsol. code
        self.enqueue( "+CREG=2" ) # registration information (TODO not all modems support that)

        self.enqueue( "+CAOC=2" ) # advice of charge: send unsol. code

        # FIXME This will fail until CFUN=4 or CFUN=1 and SIM Auth is given
        self.enqueue( "+CNMI=2,1,2,1,1" ) # buffer SMS on SIM, report new SMS after storing, report CB directly

        # GPRS
        self.enqueue( "+CGEREP=2,1" )
        self.enqueue( "+CGREG=2" )

        # calypso proprietary
        self.enqueue( "%CPI=3" ) # call progress indication: enable with call number ID, GSM Cause, and ALS
        self.enqueue( "%CSCN=1,2,1,2" ) # show service change: call control service and supplementary service
        self.enqueue( "%CSQ=1" ) # signal strength: send unsol. code
        self.enqueue( "%CBHZ=1" ) # home zone cell broadcast: activate automatic
        self.enqueue( "%CNIV=1" )
        self.enqueue( "%CGEREP=1" )
        self.enqueue( "%CGREG=3" )
        self.enqueue( "%CSTAT=1" )

        # FIXME might enable %CPRI later

    @logged
    def suspend( self, ok_callback, error_callback ):
        self.enqueue( "+CTZU=0;+CTZR=0;+CREG=0;+CNMI=2,1,0,0,0;+CGEREP=0,0;+CGREG=0;%CSQ=0;%CGEREP=0;%CGREG=0",
                      SimpleCallback( ok_callback, self ),
                      SimpleCallback( error_callback, self ) )

    @logged
    def resume( self, ok_callback, error_callback ):
        self.enqueue( "+CTZU=1;+CTZR=1;+CREG=2;+CNMI=2,1,2,1,1;+CGEREP=2,1;+CGREG=2;%CSQ=1;%CGEREP=1;%CGREG=3",
                      SimpleCallback( ok_callback, self ),
                      SimpleCallback( error_callback, self ) )
