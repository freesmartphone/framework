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

        # This modem needs a special SIM init sequence otherwise GSM 07.07 SMS commands won't succeed
        c = self._commands["sim"] = []
        c.append( "+CRRM" )
        # FIXME if this returns an error, we might have no SIM inserted
        c.append( "+EPMS?" )

        def lastCommand( self=self ):
            self.enqueue( "+EMGL=4", self.simReadyNow, self.simReadyNow )

        c.append( lastCommand )

    def simReadyNow( self, *args, **kwargs ):
        # we _should_ be ready now, alas we can't check for sure :(
        self._modem._object.ReadyStatus( True )

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
