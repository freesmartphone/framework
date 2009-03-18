#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: channel

Freescale Neptune specific modem channels
"""

__version__ = "0.8.0"
MODULE_NAME = "ogsmd.neptune_freescale"

from ogsmd.modems.abstract.channel import AbstractModemChannel

import gobject

#=========================================================================#
class EzxMuxChannel( AbstractModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractModemChannel.__init__( self, *args, **kwargs )

    def _populateCommands( self ):
        AbstractModemChannel._populateCommands( self ) # default command init

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

#=========================================================================#
class CallAndNetworkChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

        # FIXME we can't do this, since it is modem-wide (not VC-wide)
        #self.enqueue( "+CMER=0,0,0,0,0" ) # unsolicited event reporting: none

#=========================================================================#
class MiscChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

        # FIXME we can't do this, since it is modem-wide (not VC-wide)
        #self.enqueue( "+CMER=0,0,0,0,0" ) # unsolicited event reporting: none

    def modemStateSimUnlocked( self ):
        """
        Called, when the modem signalizes the SIM being unlocked.
        """

        # This modem needs a special SIM init sequence otherwise GSM 07.07 SMS commands won't succeed
        self.enqueue( "+CRRM" )
        # FIXME if this returns an error, we might have no SIM inserted
        self.enqueue( "+EPMS?" )
        self.enqueue( "+EMGL=4", self._ezxEgmlAnswer )

        return False # gobject: don't call me again

    def _ezxEgmlAnswer( self, request, response ):
        if response[-1] == "OK":
            # send SIM is ready command
            self._modem._object.ReadyStatus( True )
        else:
            gobject.timeout_add( 3, self.modemStateSimUnlocked )

#=========================================================================#
class SmsChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

#=========================================================================#
class SimChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )
