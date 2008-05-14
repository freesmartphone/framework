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
from gsm import channel, mediator, unsol
from gobject import timeout_add, idle_add

DBUS_INTERFACE_DEVICE = "org.freesmartphone.GSM.Device"
DBUS_INTERFACE_SIM = "org.freesmartphone.GSM.Sim"
DBUS_INTERFACE_NETWORK = "org.freesmartphone.GSM.Network"
DBUS_INTERFACE_CALL = "org.freesmartphone.GSM.Call"

DBUS_INTERFACE_SERVER = "org.freesmartphone.GSM.Server"
DBUS_INTERFACE_TEST = "org.freesmartphone.test"

#=========================================================================#
class Server( dbus.service.Object ):
#=========================================================================#
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
    def Foo( self ):
        return "foo"

    @dbus.service.method( DBUS_INTERFACE_SERVER, "", "s" )
    def Bar( self ):
        return "bar"

#=========================================================================#
class Device( dbus.service.Object ):
#=========================================================================#
    """
    This class handles the dbus interface of org.freesmartphone.GSM.*

    We're using the following mapping of channels to commands:
    * Channel 1: Call Handling
    * Channel 2: Unsolicited Responses (optional: keep-alive)
    * Channel 3: Miscellaneous (everything non-call)
    * Channel 4: GPRS

    Since our virtual channels can handle interleaved request/response,
    we could also send additional stuff on channel 2.
    """
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Device" )

    def __init__( self, bus, modemtype ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Device"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.channels = {}
        self.channels["CALL"] = channel.GenericModemChannel( bus, "ophoned.call" )
        self.channels["UNSOL"] = channel.UnsolicitedResponseChannel( bus, "ophoned.unsolicited" )
        self.channels["MISC"] = channel.GenericModemChannel( bus, "ophoned.misc" )

        self.channel = self.channels["MISC"] # default channel

        self.channels["UNSOL"].launchKeepAlive( 7000, "" )
        self.channels["UNSOL"].setDelegate( unsol.UnsolicitedResponseDelegate( self ) )

        idle_add( self._initChannels )

    #
    # dbus org.freesmartphone.GSM.Device
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
        mediator.DeviceSetAntennaPower( self, dbus_ok, dbus_error, power=power )

    #
    # dbus org.freesmartphone.GSM.SIM
    #

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAuthStatus( self, dbus_ok, dbus_error ):
        mediator.SimGetAuthStatus( self, dbus_ok, dbus_error )

    #
    # internal API
    #
    def _initChannels( self ):
        for channel in self.channels:
            print "trying to open", channel
            if not self.channels[channel].isOpen():
                if not self.channels[channel].open():
                    LOG( LOG_ERR, "could not open channel %s - retrying in 2 seconds" % channel )
                    gobject.timeout_add( 2000, self._initChannel )
        return False

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    import dbus
    bus = dbus.SystemBus()

    def testing( device ):
        try:
            device.GetInfo()
        except Exception, e:
            return e

    # testing 'Server'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Server" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    server = dbus.Interface(proxy, DBUS_INTERFACE_SERVER )

    # testing 'Device'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Device" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    device = dbus.Interface(proxy, DBUS_INTERFACE_DEVICE )
    sim = dbus.Interface(proxy, DBUS_INTERFACE_SIM )
    network = dbus.Interface(proxy, DBUS_INTERFACE_NETWORK )
    call = dbus.Interface(proxy, DBUS_INTERFACE_CALL )
