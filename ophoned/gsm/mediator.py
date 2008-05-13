#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: Mediator

This module needs to be overhauled completely. Since the implementation
of all non-trivial dbus calls need to launch subsequent AT commands
before the final result can be delivered, we need to come up with a
generic programmable state machine here...
"""

from decor import logged
import error
import const

#=========================================================================#
class AbstractMediator( object ):
#=========================================================================#
    @logged
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        self._object = dbus_object
        self._ok = dbus_ok
        self._error = dbus_error
        self.__dict__.update( **kwargs )
        self.trigger()

    def trigger( self ):
        assert False, "pure virtual function called"

    def responseFromChannel( self, request, response ):
        if response[-1].startswith( "ERROR" ):
            self._error( error.DeviceFailed( "command %s failed" % request ) )
        elif response[-1].startswith( "+CM" ):
            self._handleCmeCmsError( response[-1] )
        elif response[-1].startswith( "OK" ):
            self._ok()
        else:
            assert False, "should never reach that"

    @logged
    def errorFromChannel( self, request, error ):
        category, details = error
        if category == "timeout":
            self._error( error.DeviceTimeout( "device did not answer within %dms" % details ) )
        else:
            self._error( error.DeviceFailed( "%s: %s" % ( category, repr(details ) ) ) )

    @logged
    def __del__( self, *args, **kwargs ):
        pass

    def _rightHandSide( self, line ):
        try:
            result = line.split( ':', 1 )[1]
        except IndexError:
            result = line
        return result.strip( '" ' )

    def _handleCmeCmsError( self, line ):
        category, text = const.parseError( line )
        # TODO add specific exceptions
        self._error( error.DeviceFailed( "%s ERROR: %s" % ( category, text ) ) )

#=========================================================================#
class DeviceGetInfo( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        assert response[-1] == "OK"
        assert len( response ) == 5
        result = {}
        result.update( revision=self._rightHandSide( response[0] ),
                       model=self._rightHandSide( response[1] ),
                       manufacturer=self._rightHandSide( response[2] ),
                       imei=self._rightHandSide( response[3] ) )
        self._ok( result )

#=========================================================================#
class DeviceGetAntennaPower( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CFUN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            self._ok( not self._rightHandSide( response[0] ) == "0" )
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetAntennaPower( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CFUN?", self.intermediateResponse, self.errorFromChannel )

    def intermediateResponse( self, request, response ):
        assert response[-1] == "OK"
        state = self._rightHandSide( response[0] ) == "1"
        if state == self.power:
            # nothing to do
            self._ok()
        else:
            self._object.channel.enqueue( "+CFUN=%d" % self.power, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceGetFeatures( AbstractMediator ):
#=========================================================================#
    pass

#=========================================================================#
def enableModemExtensions( modem ):
#=========================================================================#
    """
    Walk through all available mediator classes
    and -- if existing -- substitute with modem specific
    classes.
    """
    pass

if __name__ == "__main__":
    pass