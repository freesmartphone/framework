#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from decor import logged
import error

#=========================================================================#
class AbstractMediator( object ):
#=========================================================================#
    @logged
    def __init__( self, dbus_object, dbus_ok, dbus_error ):
        self.object = dbus_object
        self.ok = dbus_ok
        self.error = dbus_error
        self.trigger()

    def trigger( self ):
        assert False, "pure virtual function called"

    @logged
    def __del__( self, *args, **kwargs ):
        pass

    def _rightHandSide( self, line ):
        try:
            result = line.split( ':', 1 )[1]
        except IndexError:
            result = line
        return result.strip( '" ' )

#=========================================================================#
class DeviceGetInfo( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self.object.channel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        assert response[-1] == "OK"
        assert len( response ) == 5
        result = {}
        result.update( revision=self._rightHandSide( response[0] ),
                       model=self._rightHandSide( response[1] ),
                       manufacturer=self._rightHandSide( response[2] ),
                       imei=self._rightHandSide( response[3] ) )
        self.ok( result )

    @logged
    def errorFromChannel( self, request, error ):
        category, details = error
        if category == "timeout":
            self.error( error.DeviceTimeout( "device did not answer within %dms" % details ) )
        else:
            self.error( error.DeviceFailed( "%s: %s" % ( category, repr(details ) ) ) )

#=========================================================================#
class DeviceGetAntennaPower( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self.object.channel.enqueue( "+CFUN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        assert response[-1] == "OK"
        self.ok( not self._rightHandSide( response[0] ) == "0" )

    @logged
    def errorFromChannel( self, request, error ):
        category, details = error
        if category == "timeout":
            self.error( error.DeviceTimeout( "device did not answer within %dms" % details ) )
        else:
            self.error( error.DeviceFailed( "%s: %s" % ( category, repr(details ) ) ) )


#=========================================================================#
class DeviceGetAntennaPower( AbstractMediator ):
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