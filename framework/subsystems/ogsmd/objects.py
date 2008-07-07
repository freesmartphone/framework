#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd
Module: objects

Implementation of the dbus objects.

Attributes:
    * server = server dbus object singleton
    * device = device dbus object singleton
"""

import types
from framework.config import LOG, LOG_INFO, LOG_ERR, LOG_DEBUG
import dbus
import dbus.service
from dbus import DBusException
from gobject import timeout_add, idle_add
import weakref
import sys, os

DBUS_INTERFACE_DEVICE = "org.freesmartphone.GSM.Device"
DBUS_INTERFACE_SIM = "org.freesmartphone.GSM.SIM"
DBUS_INTERFACE_NETWORK = "org.freesmartphone.GSM.Network"
DBUS_INTERFACE_CALL = "org.freesmartphone.GSM.Call"
DBUS_INTERFACE_PDP = "org.freesmartphone.GSM.PDP"

DBUS_INTERFACE_SERVER = "org.freesmartphone.GSM.Server"

DBUS_INTERFACE_TEST = "org.freesmartphone.GSM.Test"

DBUS_BUS_NAME_DEVICE = "org.freesmartphone.ogsmd"
DBUS_BUS_NAME_SERVER = "org.freesmartphone.ogsmd"

DBUS_OBJECT_PATH_DEVICE = "/org/freesmartphone/GSM/Device"
DBUS_OBJECT_PATH_SERVER = "/org/freesmartphone/GSM/Server"

#=========================================================================#
class Server( dbus.service.Object ):
#=========================================================================#
    """
    High level access to the Open Phone Server.

    Idea: Send high level readiness signals for function complexes such as:
    - PhonebookReady
    - MessagebookReady
    - CallReady
    - SmsReady

    - watch for clients on bus and send coldplug status
    - monitor device aliveness and restart, if necessary
    """

    def __init__( self, bus, device ):
        server = weakref.proxy( self )
        self.interface = DBUS_INTERFACE_SERVER
        self.path = DBUS_OBJECT_PATH_SERVER
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.device = device

    def __del__( self ):
        server = None

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE_SERVER, "", "s" )
    def Bar( self ):
        return "bar"

    # Send Diffs only
    # Caching strategy

#=========================================================================#
class Device( dbus.service.Object ):
#=========================================================================#
    """
    This class handles the dbus interface of org.freesmartphone.GSM.*

    We're using the following typical mapping of channels to commands:
    * Channel 1: Call Handling
    * Channel 2: Unsolicited Responses
    * Channel 3: Miscellaneous (everything non-call, SIM, Network, Device, SMS)
    * Channel 4: GPRS
    Since all our virtual channels handle interleaved request/response
    and unsolicited though, we can also send additional commands everywhere :)
    """

    def __init__( self, bus, modemtype ):
        self.bus = bus
        self.interface = DBUS_INTERFACE_DEVICE
        self.path = DBUS_OBJECT_PATH_DEVICE
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        if modemtype == "singleline":
            from modems.singleline.modem import SingleLine as Modem
            global mediator
            import modems.singleline.mediator as mediator
        elif modemtype == "muxed4line":
            from modems.muxed4line.modem import Muxed4Line as Modem
            global mediator
            import modems.muxed4line.mediator as mediator
        elif modemtype == "ti_calypso":
            from modems.ti_calypso.modem import TiCalypso as Modem
            global mediator
            import modems.ti_calypso.mediator as mediator
        else:
            assert False, "unsupported modem type"

        self.modem = Modem( self, bus )
        self.modem.open( self._channelsOK )

    def __del__( self ):
        """Destruct."""
        device = None

    def _channelsOK( self ):
        """Called when idle and all channels have been successfully opened."""
        print "NOTIFY SERVER: ALL CHANNELS OK, START TRAFFICING :)"
        return False # don't call again

    #
    # dbus org.freesmartphone.GSM.Device
    #
    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def CancelCommand( self, dbus_ok, dbus_error ):
        mediator.CancelCommand( self, dbus_ok, dbus_error )

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

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PrepareForSuspend( self, dbus_ok, dbus_error ):
        # FIXME no error handling yet!
        self.modem.prepareForSuspend( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RecoverFromSuspend( self, dbus_ok, dbus_error ):
        # FIXME no error handling yet!
        self.modem.recoverFromSuspend( dbus_ok, dbus_error )

    #
    # dbus org.freesmartphone.GSM.SIM
    #

    ### SIM auth
    @dbus.service.method( DBUS_INTERFACE_SIM, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAuthStatus( self, dbus_ok, dbus_error ):
        mediator.SimGetAuthStatus( self, dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_SIM, "s" )
    def AuthStatus( self, status ):
        LOG( LOG_INFO, "auth status changed to", status )

    @dbus.service.method( DBUS_INTERFACE_SIM, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SendAuthCode( self, code, dbus_ok, dbus_error ):
        mediator.SimSendAuthCode( self, dbus_ok, dbus_error, code=code )

    @dbus.service.method( DBUS_INTERFACE_SIM, "ss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Unlock( self, puk, new_pin, dbus_ok, dbus_error ):
        mediator.SimUnlock( self, dbus_ok, dbus_error, puk=puk, new_pin=new_pin )

    @dbus.service.method( DBUS_INTERFACE_SIM, "ss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ChangeAuthCode( self, old_pin, new_pin, dbus_ok, dbus_error ):
        mediator.SimChangeAuthCode( self, dbus_ok, dbus_error, old_pin=old_pin, new_pin=new_pin )

    ### SIM info
    @dbus.service.method( DBUS_INTERFACE_SIM, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetImsi( self, dbus_ok, dbus_error ):
        mediator.SimGetImsi( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSubscriberNumbers( self, dbus_ok, dbus_error ):
        mediator.SimGetSubscriberNumbers( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "ss",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSimCountryCode( self, dbus_ok, dbus_error ):
        mediator.SimGetCountryCode( self, dbus_ok, dbus_error )

    ### SIM phonebook
    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetPhonebookInfo( self, dbus_ok, dbus_error ):
        mediator.SimGetPhonebookInfo( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a(iss)",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RetrievePhonebook( self, dbus_ok, dbus_error ):
        mediator.SimRetrievePhonebook( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DeleteEntry( self, index, dbus_ok, dbus_error ):
        mediator.SimDeleteEntry( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_SIM, "iss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StoreEntry( self, index, name, number, dbus_ok, dbus_error ):
        mediator.SimStoreEntry( self, dbus_ok, dbus_error, index=index, name=name, number=number )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "ss",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RetrieveEntry( self, index, dbus_ok, dbus_error ):
        mediator.SimRetrieveEntry( self, dbus_ok, dbus_error, index=index )

    ### SIM messagebook
    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetMessagebookInfo( self, dbus_ok, dbus_error ):
        mediator.SimGetMessagebookInfo( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "s", "a(isss)",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RetrieveMessagebook( self, category, dbus_ok, dbus_error ):
        mediator.SimRetrieveMessagebook( self, dbus_ok, dbus_error, category=category )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "sss",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RetrieveMessage( self, index, dbus_ok, dbus_error ):
        mediator.SimRetrieveMessage( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetServiceCenterNumber( self, dbus_ok, dbus_error ):
        mediator.SimGetServiceCenterNumber( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetServiceCenterNumber( self, number, dbus_ok, dbus_error ):
        mediator.SimSetServiceCenterNumber( self, dbus_ok, dbus_error, number=number )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DeleteMessage( self, index, dbus_ok, dbus_error ):
        mediator.SimDeleteMessage( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_SIM, "ss", "i",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StoreMessage( self, number, contents, dbus_ok, dbus_error ):
        mediator.SimStoreMessage( self, dbus_ok, dbus_error, number=number, contents=contents )

    @dbus.service.signal( DBUS_INTERFACE_SIM, "i" )
    def NewMessage( self, index ):
        LOG( LOG_INFO, "new message on sim storage index", index )

    #
    # dbus org.freesmartphone.GSM.Network
    #
    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Register( self, dbus_ok, dbus_error ):
        mediator.NetworkRegister( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Unregister( self, dbus_ok, dbus_error ):
        mediator.NetworkUnregister( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetStatus( self, dbus_ok, dbus_error ):
        mediator.NetworkGetStatus( self, dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_NETWORK, "a{sv}" )
    def Status( self, status ):
        LOG( LOG_INFO, "org.freesmartphone.GSM.Network.Status: ", repr(status) )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "i",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSignalStrength( self, dbus_ok, dbus_error ):
        mediator.NetworkGetSignalStrength( self, dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_NETWORK, "i" )
    def SignalStrength( self, strength ):
        LOG( LOG_INFO, "org.freesmartphone.GSM.Network.SignalStrength: ", repr(strength) )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "a(isss)",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ListProviders( self, dbus_ok, dbus_error ):
        mediator.NetworkListProviders( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def RegisterWithProvider( self, operator_code, dbus_ok, dbus_error ):
        mediator.NetworkRegisterWithProvider( self, dbus_ok, dbus_error, operator_code=operator_code )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetNetworkCountryCode( self, dbus_ok, dbus_error ):
        mediator.NetworkGetCountryCode( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "s", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetCallForwarding( self, reason, dbus_ok, dbus_error ):
        mediator.NetworkGetCallForwarding( self, dbus_ok, dbus_error, reason=reason )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "sssi", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def EnableCallForwarding( self, reason, class_, number, timeout, dbus_ok, dbus_error ):
        mediator.NetworkEnableCallForwarding( self, dbus_ok, dbus_error, reason=reason, class_=class_, number=number, timeout=timeout )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "ss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DisableCallForwarding( self, reason, class_, dbus_ok, dbus_error ):
        mediator.NetworkDisableCallForwarding( self, dbus_ok, dbus_error, reason=reason, class_=class_ )
    #
    # dbus org.freesmartphone.GSM.Call
    #
    @dbus.service.signal( DBUS_INTERFACE_CALL, "isa{sv}" )
    def CallStatus( self, index, status, properties ):
        LOG( LOG_INFO, "org.freesmartphone.GSM.Call.CallStatus: ", repr(index), repr(status), repr(properties) )

    @dbus.service.method( DBUS_INTERFACE_CALL, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Activate( self, index, dbus_ok, dbus_error ):
        mediator.CallActivate( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_CALL, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ActivateConference( self, index, dbus_ok, dbus_error ):
        mediator.CallActivateConference( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_CALL, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Release( self, index, dbus_ok, dbus_error ):
        mediator.CallRelease( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_CALL, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ReleaseHeld( self, dbus_ok, dbus_error ):
        mediator.CallReleaseHeld( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_CALL, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ReleaseAll( self, dbus_ok, dbus_error ):
        mediator.CallReleaseAll( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_CALL, "ss", "i",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Initiate( self, number, type_, dbus_ok, dbus_error ):
        mediator.CallInitiate( self, dbus_ok, dbus_error, number=number, calltype=type_ )

    # FIXME not implemented yet
    @dbus.service.method( DBUS_INTERFACE_CALL, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def HoldActive( self, dbus_ok, dbus_error ):
        mediator.CallHoldActive( self, dbus_ok, dbus_error )

    # ListCalls
    # GetCallStatus
    # SendDtmf
    # SetDtmfDuration
    # GetDtmfDuration
    # SetSendID
    # GetSendID

    #
    # dbus org.freesmartphone.GSM.PDP
    #
    @dbus.service.method( DBUS_INTERFACE_PDP, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ListAvailableGprsClasses( self, dbus_ok, dbus_error ):
        mediator.PdpListAvailableGprsClasses( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_PDP, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetCurrentGprsClass( self, dbus_ok, dbus_error ):
        mediator.PdpGetCurrentGprsClass( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_PDP, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetCurrentGprsClass( self, class_, dbus_ok, dbus_error ):
        mediator.PdpSetCurrentGprsClass( self, dbus_ok, dbus_error, class_=class_ )

    @dbus.service.method( DBUS_INTERFACE_PDP, "sss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ActivateContext( self, apn, user, password, dbus_ok, dbus_error ):
        mediator.PdpActivateContext( self, dbus_ok, dbus_error, apn=apn, user=user, password=password )

    @dbus.service.method( DBUS_INTERFACE_PDP, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DeactivateContext( self, dbus_ok, dbus_error ):
        mediator.PdpDeactivateContext( self, dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_PDP, "isa{sv}" )
    def ContextStatus( self, index, status, properties ):
        LOG( LOG_INFO, "org.freesmartphone.GSM.PDP.ContextStatus: ", repr(index), repr(status), repr(properties) )

    #
    # dbus org.freesmartphone.GSM.Test
    # WARNING: DO NOT USE THIS! :)
    #
    @dbus.service.method( DBUS_INTERFACE_TEST, "s", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Command( self, command, dbus_ok, dbus_error ):
        mediator.TestCommand( self, dbus_ok, dbus_error, command=command )

    @dbus.service.method( DBUS_INTERFACE_TEST, "s", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Echo( self, echo, dbus_ok, dbus_error ):
        import time
        time.sleep( 2 )
        dbus_ok( echo )
        dbus_error( "foo" )
        dbus_ok( echo )

    @dbus.service.method( DBUS_INTERFACE_TEST, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Ping( self, dbus_ok, dbus_error ):
        dbus_ok()

#=========================================================================#
def factory( prefix, controller ):
#=========================================================================#
    sys.path.append( os.path.dirname( os.path.dirname( __file__ ) ) )
    modemtype = controller.config.get( "ogsmd", "modemtype" )
    device = Device( controller.bus, modemtype )
    server = Server( controller.bus, device )
    return device, server

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    import dbus, sys, thread, atexit
    from gobject import threads_init, MainLoop

    def handler( *args, **kwargs ):
        print "="*78
        print "got a signal from '%s' (via %s):" % ( kwargs["path"], kwargs["sender"] )
        print "=> SIGNAL: %s.%s (" % ( kwargs["interface"], kwargs["member"] ),
        for arg in args[:-1]:
            print "%s, " % arg,
        print "%s )" % args[-1]
        print "="*78

    def run( *args ):
        print "entering mainloop"
        mainloop.run()
        print "exit from mainloop"

    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
    mainloop = MainLoop()

    bus = dbus.SystemBus()

    # server
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Server", follow_name_owner_changes=True )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    server = dbus.Interface(proxy, DBUS_INTERFACE_SERVER )

    # device
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Device", follow_name_owner_changes=True )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    device = dbus.Interface( proxy, DBUS_INTERFACE_DEVICE )
    sim = dbus.Interface( proxy, DBUS_INTERFACE_SIM )
    network = dbus.Interface( proxy, DBUS_INTERFACE_NETWORK )
    call = dbus.Interface( proxy, DBUS_INTERFACE_CALL )
    test = dbus.Interface( proxy, DBUS_INTERFACE_TEST )

    peer = dbus.Interface( proxy, "org.freedesktop.DBus.Peer" )

    bus.add_signal_receiver( handler, None, None, config.DBUS_BUS_NAME, None,
        sender_keyword = "sender",
        destination_keyword = "destination",
        interface_keyword = "interface",
        member_keyword = "member",
        path_keyword = "path" )

    threads_init()
    thread.start_new_thread( run, () )

