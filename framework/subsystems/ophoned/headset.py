# -*- coding: UTF-8 -*-
"""
Open Phone Daemon - BlueZ headset interface

(C) 2009 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2009 Openmoko, Inc.
GPLv2 or later

Package: ophoned
Module: headset

FIXME: This is still device specific...

"""

__version__ = "0.9.0.0"
MODULE_NAME = "ophoned.headset"

import dbus, alsaaudio, gobject, subprocess

import logging
logger = logging.getLogger( MODULE_NAME )

class HeadsetError( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Phone.HeadsetError"

class HeadsetManager( object ):
    def __init__( self, bus, onAnswerRequested = None, onConnectionStatus = None ):
        self.bus = bus
        self._onAnswerRequested = onAnswerRequested
        self._matchAnswerRequested = None
        self._onConnectionStatus = onConnectionStatus
        self._matchDisconnected = None
        self.address = None
        self.pcm_device = "hw:0,1"
        self.pcm_play = None
        self.pcm_cap = None
        self.connected = False
        self.playing = False
        self._kickPCM()
        usage = self.bus.get_object( 'org.freesmartphone.ousaged', '/org/freesmartphone/Usage', follow_name_owner_changes=True )
        self.usageiface = dbus.Interface( usage, 'org.freesmartphone.Usage' )
        logger.info( "usage ok: %s" % self.usageiface )


    def _kickPCM( self ):
        try:
            hpcm_play = alsaaudio.PCM( alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NONBLOCK, "hw:0,0" )
            hpcm_cap = alsaaudio.PCM( alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, "hw:0,0" )
            del hpcm_play
            del hpcm_cap
        except alsaaudio.ALSAAudioError:
            pass

    def _startPCM( self ):
        self._stopPCM()

        self.pcm_play = alsaaudio.PCM( alsaaudio.PCM_PLAYBACK, alsaaudio.PCM_NONBLOCK, self.pcm_device )
        self.pcm_play.setchannels(1)
        self.pcm_play.setrate(8000)
        self.pcm_play.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self.pcm_play.setperiodsize(500000)

        self.pcm_cap = alsaaudio.PCM( alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NONBLOCK, self.pcm_device )
        self.pcm_cap.setchannels(1)
        self.pcm_cap.setrate(8000)
        self.pcm_cap.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        self.pcm_cap.setperiodsize(500000)

    def _stopPCM( self ):
        if not self.pcm_play is None:
            self.pcm_play.close()
            self.pcm_play = None
        if not self.pcm_cap is None:
            self.pcm_cap.close()
            self.pcm_cap = None

    def _connectBT( self ):
        bluez_manager_proxy = self.bus.get_object(
            "org.bluez",
            "/",
        )
        self.bluez_manager = dbus.Interface(
            bluez_manager_proxy,
            "org.bluez.Manager",
        )
        bluez_adapter_proxy = self.bus.get_object(
            "org.bluez",
            self.bluez_manager.DefaultAdapter(),
        )
        self.bluez_adapter = dbus.Interface(
            bluez_adapter_proxy,
            "org.bluez.Adapter",
        )
        bluez_device_proxy = self.bus.get_object(
            "org.bluez",
            self.bluez_adapter.FindDevice( self.address ),
        )
        self.bluez_device_headset = dbus.Interface(
            bluez_device_proxy,
            "org.bluez.Headset",
        )
        self.bluez_device_headset.Connect(
            reply_handler=self.cbHeadsetConnetReply,
            error_handler=self.cbHeadsetConnectError
        )

    def cbHeadsetConnectError( self, e ):
        if e.get_dbus_name() == "org.bluez.Error.AlreadyConnected":
            self.cbHeadsetConnetReply()
        else:
            logger.info( "BT connect error" )
            raise

    def cbHeadsetConnetReply( self ):
        logger.info( "BT connect ok" )
        if self._onAnswerRequested:
            self._matchAnswerRequested = self.bluez_device_headset.connect_to_signal(
                'AnswerRequested', self._onAnswerRequested
            )
        self._matchDisconnected = self.bluez_device_headset.connect_to_signal(
                'Disconnected', self._onDisconnected
        )
        self.connected = True
        if self._onConnectionStatus:
            self._onConnectionStatus( self.connected )

    def _startBT( self ):
        try:
            self.bluez_device_headset.Play()
        except dbus.exceptions.DBusException, e:
            if e.get_dbus_name() == "org.bluez.Error.AlreadyConnected":
                pass
            else:
                raise

    def _stopBT( self ):
        self.bluez_device_headset.Stop()

    def _disconnectBT( self ):
        if self._matchAnswerRequested:
            self._matchAnswerRequested.remove()
            self._matchAnswerRequested = None
        if self._matchDisconnected:                                                                                             
            self._matchDisconnected.remove()                                                                                     
            self._matchDisconnected = None 
        # if disconnect fails for any reason, we
        # still cancel all BT, such that the audio
        # will get routed back to the headset
        try:
            self.bluez_device_headset.Disconnect()
        except:
            pass
        self.bluez_device_headset = None
        self.bluez_adapter = None
        self.bluez_manager = None
        self.connected = False
        if self._onConnectionStatus:                                           
            self._onConnectionStatus( self.connected )

    def _onDisconnected( self ):
        self._disconnectBT()
        logger.info( "got disconnected" )
        if self.address:
           self.monitor = gobject.timeout_add_seconds( 10, self._handleMonitorTimeout )

    def _updateConnected( self ):
        if self.address and not self.connected:
            self._connectBT()

    def _handleMonitorTimeout( self ):
        try:
            self._updateConnected()
        except:
            logger.debug( "_handleMonitorTimeout failed:", exc_info=True )
        if self.address and not self.connected:
           return True
        else:
           return False

    def setAddress( self, address ):
        if self.address != address:
            if self.connected:
                self.setPlaying( False )
                self._disconnectBT()
        if self.address and not address:
            self.usageiface.ReleaseResource(
                "Bluetooth",
                reply_handler=self.cbReleaseReply,
                error_handler=self.cbReleaseError,
            )
        if not self.address and address:
            try:
                self.usageiface.RequestResource(
                    "Bluetooth",
                    reply_handler=self.cbRequestReply,
                    error_handler=self.cbRequestError,
                )
            except:
                pass
            self.monitor = gobject.timeout_add_seconds( 10, self._handleMonitorTimeout )
        self.address = address

    def cbRequestReply( self ):
        logger.info( "Requested Bluetooth" )

    def cbRequestError( self, e ):
        log_dbus_error( e, "error while requesting Bluetooth"  )
        logger.info( "Requested Bluetooth with error" )

    def cbReleaseReply( self ):
        logger.info( "Released Bluetooth" )

    def cbReleaseError( self, e ):
        log_dbus_error( e, "error while releasing Bluetooth" )
        logger.info( "Released Bluetooth with error" )

    def getConnected( self ):
        return self.connected

    def setPlaying( self, playing ):
        if not self.playing and playing:
            if not self.connected:
                raise HeadsetError("No connected")
            self._startPCM()
            self._startBT()
            self.playing = True
        elif self.playing and not playing:
            self._stopBT()
            self._stopPCM()
            self.playing = False

    def getPlaying( self ):
        return self.playing

if __name__=="__main__":
    m = HeadsetManager( dbus.SystemBus() )


