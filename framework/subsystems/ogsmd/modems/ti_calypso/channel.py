#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
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

import logging
logger = logging.getLogger('ogsmd')

from ogsmd.gsm.decor import logged
from ogsmd.gsm.callback import SimpleCallback

from ogsmd.modems.abstract.channel import AbstractModemChannel

#=========================================================================#
class CalypsoModemChannel( AbstractModemChannel ):
#=========================================================================#
    modem_communication_timestamp = 1

    def __init__( self, *args, **kwargs ):
        AbstractModemChannel.__init__( self, *args, **kwargs )

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
            logger.debug( "(modem init... try #%d)", i+1 )
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
                logger.debug( "read: %s", ok )
                if "OK" in ok or "AT" in ok:
                    break
            logger.debug( "(modem not responding)" )
            if i == 5:
                logger.debug( "(reopening modem)" )
                self.serial.close()
                path = self.pathfactory()
                if not path: # path is None or ""
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                logger.warning( "(can't read from modem. giving up)" )
                self.serial.close()
                return False
        logger.info( "(modem responding)" )
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
                logger.debug( "(%s: last communication with modem was %d seconds ago. Sending EOF to wakeup)", self, int(current_time - CalypsoModemChannel.modem_communication_timestamp) )
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

    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )
        self._commands["sim"] = []
        self._commands["antenna"] = []

    def setIntermediateResponseCallback( self, callback ):
        assert self.callback is None, "callback already set"
        self.callback = callback

    def handleUnsolicitedResponse( self, response ):
        if self.callback is not None:
            self.callback( response )
        else:
            logger.warning( "CALLCHANNEL: UNHANDLED INTERMEDIATE: %s", response )

#=========================================================================#
class MiscChannel( CalypsoModemChannel ):
#=========================================================================#
    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )
        self._commands["sim"] = []
        self._commands["antenna"] = []

#=========================================================================#
class UnsolicitedResponseChannel( CalypsoModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        CalypsoModemChannel.__init__( self, *args, **kwargs )

    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )

        c = self._commands["init"]
        # GSM unsolicited
        c.append( '+CLIP=1' ) # calling line identification presentation enable
        c.append( '+COLP=1' ) # connected line identification presentation enable
        c.append( '+CCWA=1' ) # call waiting
        c.append( "+CSSN=1,1" ) # supplementary service notifications: send unsol. code
        c.append( '+CTZU=1' ) # timezone update
        c.append( '+CTZR=1' ) # timezone reporting
        c.append( '+CREG=2' ) # registration information (NOTE not all modems support =2)
        c.append( "+CAOC=2" ) # advice of charge: send unsol. code
        # GPRS unsolicited
        c.append( "+CGEREP=2,1" )
        c.append( "+CGREG=2" )
        # calypso proprietary unsolicited
        c.append( "%CPI=3" ) # call progress indication: enable with call number ID, GSM Cause, and ALS
        c.append( "%CSCN=1,2,1,2" ) # show service change: call control service and supplementary service
        c.append( "%CSQ=1" ) # signal strength: send unsol. code
        c.append( "%CNIV=1" )
        c.append( "%CGEREP=1" )
        c.append( "%CGREG=3" )
        c.append( "%CSTAT=1" )
        c.append( '@ST="-26"' ) # audio side tone: set to minimum
        # FIXME might enable %CPRI later

        c = self._commands["sim"]
        c.append( "%CBHZ=1" ) # home zone cell broadcast: activate automatic (send frequently, not just once)

        c = self._commands["suspend"]
        c.append( "+CTZU=0" )
        c.append( "+CTZR=0" )
        c.append( "+CREG=0" )
        c.append( "+CGREG=0" )
        c.append( "+CGEREP=0,0" )
        c.append( "+CNMI=2,1,0,0,0" )
        c.append( "%CSQ=0" )
        c.append( "%CGEREP=0" )
        c.append( "%CGREG=0" )

        c = self._commands["resume"]
        c.append( "+CTZU=1" )
        c.append( "+CTZR=1" )
        c.append( "+CREG=2" )
        c.append( "+CGREG=2" )
        c.append( "+CGEREP=2,1" )
        c.append( "+CNMI=2,1,2,1,1" )
        c.append( "%CSQ=1" ) # signal strength: send unsol. code
        c.append( "%CNIV=1" )
        c.append( "%CGEREP=1" )
        c.append( "%CGREG=3" )

