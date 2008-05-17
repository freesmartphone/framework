#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from decor import logged
import const
import mediator

#=========================================================================#
class UnsolicitedResponseDelegate( object ):
#=========================================================================#

    @logged
    def __init__( self, dbus_object ):
        self._object = dbus_object

    def _sendStatus( self ):
        self._object.Status( self.operator, self.register, self.strength )

    #
    # unsolicited callbacks
    #

    def plusCREG( self, righthandside ):
        values = righthandside.split( ',' )
        self.register = const.REGISTER_STATUS[int(values[0])]
        if len( values ) == 3:
            self.la = values[1].strip( '"' )
            self.ci = values[2].strip( '"' )

        mediator.NetworkGetStatus( self._object, self.statusOK, self.statusERR )

    def percentCSQ( self, righthandside ):
        values = righthandside.split( ',' )
        #self.strength = const.signalQualityToPercentage( int(values[0]) )
        #self._sendStatus()


    #
    # helpers
    #

    def statusOK( self, provider_name, status, strength ):
        self._object.Status( provider_name, status, strength )

    def statusERR( self, values ):
        print "error... ignoring"
