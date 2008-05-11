#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import types
import config
from config import LOG, LOG_INFO, LOG_ERR, LOG_DEBUG
import dbus
import dbus.service
from dbus import DBusException
from gsm import channel
from gobject import timeout_add, idle_add

from gsm import mediator

DBUS_INTERFACE_DEVICE = "org.freesmartphone.GSM.Device"
DBUS_INTERFACE_SIM = "org.freesmartphone.GSM.Sim"
DBUS_INTERFACE_NETWORK = "org.freesmartphone.GSM.Network"
DBUS_INTERFACE_CALL = "org.freesmartphone.GSM.Call"

DBUS_INTERFACE_SERVER = "org.freesmartphone.GSM.Server"
DBUS_INTERFACE_TEST = "org.freesmartphone.test"

class Server( dbus.service.Object ):
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Server" )

    def __init__( self, bus, device ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Server"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.device = device

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE_TEST, "", "s" )
    def GetVersion( self ):
        return "foo"

    @dbus.service.method( DBUS_INTERFACE_SERVER, "", "s" )
    def GetVersion( self ):
        return "bar"

class AbstractAsyncResponse( object ):
    def __init__( self, dbus_result, dbus_error ):
        self.dbus_result = dbus_result
        self.dbus_error = dbus_error
        print "(async response object %s generated)" % self

    def handleResult( self, *args ):
        assert False, "Pure Virtual Function called"

    def handleError( self, *args ):
        print "(async: handle error)", repr(args)

    def handleCmeError( self, number, string ):
        print "(async: handle cme error)", repr(number), repr(string)

    def handleCmsError( self, number, string ):
        print "(async: handle cms error)", repr(number), repr(string)

    def __del__( self ):
        print "(async response object %s destroyed)" % self

class AsyncResponseNone( AbstractAsyncResponse ):
    def handleResult( self, *args ):
        self.dbus_result( None )
    def handleError( self, *args ):
        print "(async: handle error)", repr(args)
        e = DBusException( "foo", "bar", "yo", "offenbar beliebig viele Parameter".split() )
        self.dbus_error( e )

class AsyncResponseBool( AbstractAsyncResponse ) :
    def handleResult( self, answer, result ):
        self.dbus_result( result == 1 )

class AsyncMultipleResponseDict( AbstractAsyncResponse ):
    def __init__( self, dbus_result, dbus_error ):
        AbstractAsyncResponse.__init__( self, dbus_result, dbus_error )
        self.expected = {}
        self.result = {}

    def addResponse( self, response, resultkey ):
        assert response not in self.expected, "duplicated response key '%s'" % response
        assert type( resultkey ) == types.StringType, "resultkey needs to be a string"
        self.expected[response] = resultkey

    def handleResult( self, question, response ):
        print "have been called for question=", repr(question), "response=", repr(response)
        print "self.expected=", repr( self.expected )
        print "self.result=", repr( self.result )
        assert question in self.expected, "got unexpected reply '%s'" % question
        self.result[self.expected[question]] = response
        del self.expected[question]
        print "self.expected keys now=", repr(self.expected.keys())
        if not self.expected:
            self.dbus_result( self.result )

class Device( dbus.service.Object ):
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Device" )

    def __init__( self, bus, modemClass ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Device"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.channel = channel.GenericModemChannel( bus )

        idle_add( self._initChannel )

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetInfo( self, dbus_ok, dbus_error ):
        mediator.DeviceGetInfo( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetFeatures( self, dbus_ok, dbus_error ):
        mediator.DeviceGetFeatures( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "b",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAntennaPower( self, dbus_ok, dbus_error ):
        mediator.DeviceGetAntennaPower( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "b", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetAntennaPower( self, power, dbus_ok, dbus_error ):
        mediator.DeviceSetAntennaPower( self, dbus_ok, dbus_error )

    #
    # internal API
    #
    def _initChannel( self ):
        if not self.channel.open():
            LOG( LOG_ERR, "could not open modem channel - retrying in 2 seconds" )
            gobject.timeout_add( 2000, self._initChannel )
        return False

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    # testing 'Server'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Server" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    server = dbus.Interface(proxy, Server.DBUS_INTERFACE )

    # testing 'Device'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Device" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    device = dbus.Interface(proxy, Device.DBUS_INTERFACE )

