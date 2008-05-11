#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from decor import logged

#=========================================================================#
class DeviceGetInfo( object ):
#=========================================================================#

    @logged
    def __init__( self, dbus_object, dbus_ok, dbus_error ):
        self.object = dbus_object
        self.ok = dbus_ok
        self.error = dbus_error

        assert hasattr( dbus_object, "channel" ), "dbus server object not properly configured"

        self.object.channel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        print "*** got response to", request, "from Channel", response
        self.ok( {"response": response} )

    @logged
    def errorFromChannel( self, request, err ):
        print "*** got error to", request, "from Channel", err
        self.error( "timeout" )

    @logged
    def __del__( self, *args, **kwargs ):
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