#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: channel

Freescale Neptune specific modem channels
"""


from ogsmd.modems.abstract.channel import AbstractModemChannel
from ogsmd.gsm.parser import ThrowStuffAwayParser

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
class MiscChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )

        # FIXME we can't do this, since it is modem-wide (not VC-wide)
        #self.enqueue( "+CMER=0,0,0,0,0" ) # unsolicited event reporting: none

    def installParser( self ):
        trash = [ "+CIEV:" ]
        self.parser = ThrowStuffAwayParser( trash, self._handleResponseToRequest, self._handleUnsolicitedResponse )

#=========================================================================#
class UnsolicitedResponseChannel( EzxMuxChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        EzxMuxChannel.__init__( self, *args, **kwargs )
