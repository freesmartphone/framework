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
import math
import sys, os

import logging
logger = logging.getLogger('ogsmd')

DBUS_INTERFACE_DEVICE = "org.freesmartphone.GSM.Device"
DBUS_INTERFACE_SIM = "org.freesmartphone.GSM.SIM"
DBUS_INTERFACE_NETWORK = "org.freesmartphone.GSM.Network"
DBUS_INTERFACE_CALL = "org.freesmartphone.GSM.Call"
DBUS_INTERFACE_PDP = "org.freesmartphone.GSM.PDP"
DBUS_INTERFACE_CB = "org.freesmartphone.GSM.CB"

DBUS_INTERFACE_SERVER = "org.freesmartphone.GSM.Server"
DBUS_INTERFACE_HZ = "org.freesmartphone.GSM.HZ"

DBUS_INTERFACE_DEBUG = "org.freesmartphone.GSM.Debug"

DBUS_BUS_NAME_DEVICE = "org.freesmartphone.ogsmd"
DBUS_BUS_NAME_SERVER = "org.freesmartphone.ogsmd"

DBUS_OBJECT_PATH_DEVICE = "/org/freesmartphone/GSM/Device"
DBUS_OBJECT_PATH_SERVER = "/org/freesmartphone/GSM/Server"

DEBUG = False   # TODO: remove this

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
        logger.info( "%s initialized. Serving %s at %s", self.__class__.__name__, self.interface, self.path )
        self.bus = bus
        self.homezones = None
        self.zone = "unknown"
        self.setupSignals()

    def setupSignals( self ):
        device = self.bus.get_object( DBUS_BUS_NAME_DEVICE, DBUS_OBJECT_PATH_DEVICE )
        self.fso_cb = dbus.Interface( device, DBUS_INTERFACE_CB )
        self.fso_cb.connect_to_signal( "IncomingCellBroadcast", self.onIncomingCellBroadcast )
        self.fso_sim = dbus.Interface( device, DBUS_INTERFACE_SIM )

    def __del__( self ):
        server = None

    #
    # signal handlers
    #
    def onIncomingCellBroadcast( self, channel, data ):

        def gotHomezones( homezones, self=self ):
            logger.info( "got SIM homezones: %s", homezones )
            self.homezones = homezones
            # debug code, if you have no homezones on your SIM. To test, use:
            # gsm.DebugInjectString("UNSOL","+CBM: 16,221,0,1,1\r\n347747555093\r\r\r\n")
            if DEBUG: self.homezones = [ ( "city", 347747, 555093, 1000 ), ( "home", 400000, 500000, 1000 ) ]
            self.checkInHomezones()

        if channel == 221: # home zone cell broadcast
            if len( data ) != 12:
                return
            self.x, self.y = int( data[:6] ), int( data[6:] )
            logger.info( "home zone cell broadcast detected: %s %s", self.x, self.y )
            if self.homezones is None: # never tried to read them
                logger.info( "trying to read home zones from SIM" )
                self.fso_sim.GetHomeZones( reply_handler=gotHomezones, error_handler=lambda error:None )
            else:
                self.checkInHomezones()

    def checkInHomezones( self ):
        status = ""
        for zname, zx, zy, zr in self.homezones:
            if self.checkInHomezone( self.x, self.y, zx, zy, zr ):
                status = zname
                break
        self.HomeZoneStatus( status )

    def checkInHomezone( self, x, y, zx, zy, zr ):
        logger.info( "matching %s %s %s %s %s %s %s %s", x, y, "with", zx, zy, "(", zr, ")" )
        dist = math.sqrt( math.pow( x-zx, 2 ) + math.pow( y-zy, 2 ) ) * 10
        maxdist = math.sqrt( zr ) * 10
        return dist < maxdist

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE_HZ, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetHomeZoneStatus( self, dbus_ok, dbus_error ):
        dbus_ok( self.zone )

    @dbus.service.signal( DBUS_INTERFACE_HZ, "s" )
    def HomeZoneStatus( self, zone ):
        self.zone = zone
        logger.info( "home zone status now %s", zone )

    @dbus.service.method( DBUS_INTERFACE_HZ, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetKnownHomeZones( self, dbus_ok, dbus_error ):

        def gotHomezones( homezones, self=self, dbus_ok=dbus_ok ):
            logger.info( "got SIM homezones: %s", homezones )
            self.homezones = homezones
            # debug code, if you have no homezones on your SIM. To test, use:
            # gsm.DebugInjectString("UNSOL","+CBM: 16,221,0,1,1\r\n347747555093\r\r\r\n")
            if DEBUG: self.homezones = [ ( "city", 347747, 555093, 1000 ), ( "home", 400000, 500000, 1000 ) ]
            dbus_ok( [ zone[0] for zone in self.homezones ] )

        self.fso_sim.GetHomeZones( reply_handler=gotHomezones, error_handler=lambda error:None )

    # Send Diffs only
    # Caching strategy

#=========================================================================#
class Device( dbus.service.Object ):
#=========================================================================#
    """
    This class handles the dbus interface of org.freesmartphone.GSM.*
    """

    def __init__( self, bus, modemtype ):
        self.bus = bus
        self.interface = DBUS_INTERFACE_DEVICE
        self.path = DBUS_OBJECT_PATH_DEVICE
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s initialized. Serving %s at %s", self.__class__.__name__, self.interface, self.path )

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
        elif modemtype == "freescale_neptune":
            from modems.freescale_neptune.modem import FreescaleNeptune as Modem
            global mediator
            import modems.freescale_neptune.mediator as mediator
        elif modemtype == "sierra":
            from modems.sierra.modem import Sierra as Modem
            global mediator
            import modems.sierra.mediator as mediator
        else:
            logger.error( "Unsupported modem type %s", modemtype )
            return

        self.modem = Modem( self, bus )
        self.modem.open( self._channelsOK )

    def __del__( self ):
        """Destruct."""
        device = None

    def _channelsOK( self ):
        """Called when idle and all channels have been successfully opened."""
        logger.info( "NOTIFY SERVER: ALL CHANNELS OK, START TRAFFICING :)" )
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
        logger.info( "auth status changed to %s", status )
        self.modem.setSimPinState( status )

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

    @dbus.service.method( DBUS_INTERFACE_SIM, "bs", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetAuthCodeRequired( self, required, pin, dbus_ok, dbus_error ):
        mediator.SimSetAuthCodeRequired( self, dbus_ok, dbus_error, required=required, pin=pin )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "b",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAuthCodeRequired( self, dbus_ok, dbus_error ):
        mediator.SimGetAuthCodeRequired( self, dbus_ok, dbus_error )

    ### SIM info and low-level access
    @dbus.service.method( DBUS_INTERFACE_SIM, "", "b",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSimReady( self, dbus_ok, dbus_error ):
        dbus_ok( self.modem.simReady() == True )

    @dbus.service.signal( DBUS_INTERFACE_SIM, "b" )
    def ReadyStatus( self, status ):
        logger.info( "sim ready status %s", status )
        self.modem.setSimReady( status )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a{sv}",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSimInfo( self, dbus_ok, dbus_error ):
        mediator.SimGetSimInfo( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_SIM, "s", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SendGenericSimCommand( self, command, dbus_ok, dbus_error ):
        mediator.SimSendGenericSimCommand( self, dbus_ok, dbus_error, command=command )

    @dbus.service.method( DBUS_INTERFACE_SIM, "iiiiis", "iis",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SendRestrictedSimCommand( self, command, fileid, p1, p2, p3, data, dbus_ok, dbus_error ):
        mediator.SimSendRestrictedSimCommand( self, dbus_ok, dbus_error, command=command, fileid=fileid, p1=p1, p2=p2, p3=p3, data=data )

    @dbus.service.method( DBUS_INTERFACE_SIM, "", "a(siii)",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetHomeZones( self, dbus_ok, dbus_error ):
        mediator.SimGetHomeZones( self, dbus_ok, dbus_error )

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

    @dbus.service.method( DBUS_INTERFACE_SIM, "ss", "i",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StoreMessage( self, number, contents, dbus_ok, dbus_error ):
        mediator.SimStoreMessage( self, dbus_ok, dbus_error, number=number, contents=contents )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SendStoredMessage( self, index, dbus_ok, dbus_error ):
        mediator.SimSendStoredMessage( self, dbus_ok, dbus_error, index=index )

    @dbus.service.method( DBUS_INTERFACE_SIM, "i", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DeleteMessage( self, index, dbus_ok, dbus_error ):
        mediator.SimDeleteMessage( self, dbus_ok, dbus_error, index=index )

    @dbus.service.signal( DBUS_INTERFACE_SIM, "i" )
    def NewMessage( self, index ):
        logger.info( "new message on sim storage index %s", index )

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
        logger.info( "org.freesmartphone.GSM.Network.Status: %s", status )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "i",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetSignalStrength( self, dbus_ok, dbus_error ):
        mediator.NetworkGetSignalStrength( self, dbus_ok, dbus_error )

    @dbus.service.signal( DBUS_INTERFACE_NETWORK, "i" )
    def SignalStrength( self, strength ):
        logger.info( "org.freesmartphone.GSM.Network.SignalStrength: %s", strength )

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

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetCallingIdentification( self, dbus_ok, dbus_error ):
        mediator.NetworkGetCallingIdentification( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_NETWORK, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetCallingIdentification( self, status, dbus_ok, dbus_error ):
        mediator.NetworkSetCallingIdentification( self, dbus_ok, dbus_error, status=status )
    #
    # dbus org.freesmartphone.GSM.Call
    #
    @dbus.service.signal( DBUS_INTERFACE_CALL, "isa{sv}" )
    def CallStatus( self, index, status, properties ):
        logger.info( "org.freesmartphone.GSM.Call.CallStatus: %s %s %s", index, status, properties )

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

    @dbus.service.method( DBUS_INTERFACE_CALL, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def HoldActive( self, dbus_ok, dbus_error ):
        mediator.CallHoldActive( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_CALL, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Transfer( self, number, dbus_ok, dbus_error ):
        mediator.CallTransfer( self, dbus_ok, dbus_error, number=number )

    @dbus.service.method( DBUS_INTERFACE_CALL, "", "a(isa{sv})",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ListCalls( self, dbus_ok, dbus_error ):
        mediator.CallListCalls( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_CALL, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SendDtmf( self, tones, dbus_ok, dbus_error ):
        mediator.CallSendDtmf( self, dbus_ok, dbus_error, tones=tones )

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
        logger.info( "org.freesmartphone.GSM.PDP.ContextStatus: %s %s %s", index, status, properties )

    #
    # dbus org.freesmartphone.GSM.CB
    #
    @dbus.service.method( DBUS_INTERFACE_CB, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetCellBroadcastSubscriptions( self, dbus_ok, dbus_error ):
        mediator.CbGetCellBroadcastSubscriptions( self, dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_CB, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetCellBroadcastSubscriptions( self, channels, dbus_ok, dbus_error ):
        mediator.CbSetCellBroadcastSubscriptions( self, dbus_ok, dbus_error, channels=channels )

    @dbus.service.signal( DBUS_INTERFACE_CB, "is" )
    def IncomingCellBroadcast( self, channel, data ):
        logger.info( "org.freesmartphone.GSM.CB.IncomingCellBroadcast: %s %s", channel, data )

    #
    # dbus org.freesmartphone.GSM.Debug
    # WARNING: DO NOT USE THIS! :)
    #
    @dbus.service.method( DBUS_INTERFACE_DEBUG, "s", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DebugCommand( self, command, dbus_ok, dbus_error ):
        mediator.DebugCommand( self, dbus_ok, dbus_error, command=command )

    @dbus.service.method( DBUS_INTERFACE_DEBUG, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DebugListChannels( self, dbus_ok, dbus_error ):
        dbus_ok( self.modem.channels() )

    @dbus.service.method( DBUS_INTERFACE_DEBUG, "ss", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DebugInjectString( self, channel, string, dbus_ok, dbus_error ):
        self.modem.inject( channel, str(string) )
        dbus_ok()

    @dbus.service.method( DBUS_INTERFACE_DEBUG, "s", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def DebugEcho( self, echo, dbus_ok, dbus_error ):
        import time
        time.sleep( 2 )
        dbus_ok( echo )
        dbus_error( "foo" )
        dbus_ok( echo )

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

