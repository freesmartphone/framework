#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.singeline
Module: channel
"""

from ogsmd.modems.abstract.channel import AbstractModemChannel

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
        # reenable unsolicited responses, we don't have a seperate channel
        # so we need to process them here as well
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
