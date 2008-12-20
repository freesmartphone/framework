#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.qualcomm_msm
Module: channel
"""

MODULE_NAME = "ogsmd.modems.qualcomm_msm.channel"

from ogsmd.modems.abstract.channel import AbstractModemChannel

import itertools, select

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class SingleLineChannel( AbstractModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60
        AbstractModemChannel.__init__( self, *args, **kwargs )

    def _populateCommands( self ):
        """
        Populate the command queues to be sent on modem state changes.
        """

        AbstractModemChannel._populateCommands( self ) # prepopulated

        c = self._commands["init"]
        c.remove( "Z" ) # do not reset, otherwise it will fall back to V1
        # reenable unsolicited responses, we don't have a seperate channel
        # so we need to process them here as well
        c.append( "+CLIP=1" ) # calling line identification presentation enable
        c.append( "+COLP=1" ) # connected line identification presentation enable
        c.append( "+CCWA=1" ) # call waiting
        c.append( "+CSSN=1,1" ) # supplementary service notifications: send unsol. code
        c.append( "+CTZU=1" ) # timezone update
        c.append( "+CTZR=1" ) # timezone reporting
        c.append( "+CREG=2" ) # registration information (NOTE not all modems support =2)
        c.append( "+CAOC=2" ) # advice of charge: send unsol. code
        # GPRS unsolicited
        c.append( "+CGEREP=2,1" )
        c.append( "+CGREG=2" )

    def _hookLowLevelInit( self ):
        """
        Low level initialization of channel.

        Qualcomm default mode is V0, which completely disturbs our parser.
        We send a special init here until it responds in V1 mode.
        """
        for i in itertools.count():
            logger.debug( "(modem init... try #%d)", i+1 )
            select.select( [], [self.serial.fd], [], 0.5 )
            self.serial.write( "ATE0Q0V1\r\n" )
            r, w, x = select.select( [self.serial.fd], [], [], 0.5 )
            if r:
                try:
                    buf = self.serial.inWaiting()
                # FIXME remove catchall here
                except:
                    self.serial.close()
                    path = self.pathfactory( self.name )
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
                path = self.pathfactory( self.name )
                if not path: # path is None or ""
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                logger.warning( "(can't read from modem. giving up)" )
                self.serial.close()
                return False
        logger.info( "%s: responding OK" % self )
        self.serial.flushInput()

        return True
