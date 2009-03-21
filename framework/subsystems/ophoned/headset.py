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
        self.address = None
        self.pcm_device = "hw:0,1"
        self.pcm_play = None
        self.pcm_cap = None
        self.enabled = False
        self.connected = False
        self.playing = False
        self._kickPCM()
        self.monitor = gobject.timeout_add_seconds( 10, self._handleMonitorTimeout )

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
        try:
            self.bluez_device_headset.Connect()
            if self._onAnswerRequested:
                self._matchAnswerRequested = self.bluez_device_headset.connect_to_signal(
                    'AnswerRequested', self._onAnswerRequested
                )
        except dbus.exceptions.DBusException, e:
            if e.get_dbus_name() == "org.bluez.Error.AlreadyConnected":
                pass
            else:
                raise

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
        self.bluez_device_headset.Disconnect()
        self.bluez_device_headset = None
        self.bluez_adapter = None
        self.bluez_manager = None

    def _updateConnected( self ):
        # FIXME: handle disappearing BT device
        if self.enabled and not self.connected:
            self._connectBT()
            self.connected = True
            if self._onConnectionStatus:
                self._onConnectionStatus( self.connected )
        elif not self.enabled and self.connected:
            self._disconnectBT()
            self.connected = False
            if self._onConnectionStatus:
                self._onConnectionStatus( self.connected )

    def _handleMonitorTimeout( self ):
        try:
            self._updateConnected()
        except:
            logger.exception( "_handleMonitorTimeout failed:" )
        return True

    def setAddress( self, address ):
        if self.enabled:
            raise HeadsetError("Can't change address while enabled")
        self.address = address

    def setEnabled( self, enabled ):
        if not self.enabled and enabled:
            if not self.address:
                raise HeadsetError("Address not set")
            self.enabled = True
            self._updateConnected()
        elif self.enabled and not enabled:
            self.setPlaying( False )
            self.enabled = False
            self._updateConnected()

    def getEnabled( self ):
        return self.enabled

    def getConnected( self ):
        return self.connected

    def setPlaying( self, playing ):
        if not self.playing and playing:
            if not self.enabled:
                raise HeadsetError("Not enabled")
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

