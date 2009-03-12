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

import dbus, alsaaudio

class HeadsetError( dbus.DBusException ):
    _dbus_error_name = "org.freesmartphone.Phone.HeadsetError"

class HeadsetManager( object ):
    def __init__( self, bus ):
        self.bus = bus
        self.address = None
        self.pcm_device = "hw:0,1"
        self.pcm_play = None
        self.pcm_cap = None
        self.enabled = False
        self.playing = False

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
        except dbus.exceptions.DBusException as e:
            if e.get_dbus_name() == "org.bluez.Error.AlreadyConnected":
                pass
            else:
                raise

    def _startBT( self ):
        self.bluez_device_headset.Play()

    def _stopBT( self ):
        self.bluez_device_headset.Stop()

    def _disconnectBT( self ):
        self.bluez_device_headset.Disconnect()

    def setAddress( self, address ):
        if self.enabled:
            raise HeadsetError("Can't change address while enabled")
        self.address = address

    def setEnabled( self, enabled ):
        if not self.enabled and enabled:
            if not self.address:
                raise HeadsetError("Address not set")
            # we expect bluetooth to be enabled already, should we request the resource here?
            self._connectBT()
            self.enabled = True
        elif self.enabled and not enabled:
            self.setPlaying( False )
            self.enabled = False
            self._disconnectBT()

    def setPlaying( self, playing ):
        if not self.enabled:
            raise HeadsetError("Not enabled")
        if not self.playing and playing:
            self._startPCM()
            self._startBT()
            self.playing = True
        elif self.playing and not playing:
            self._stopBT()
            self._stopPCM()
            self.playing = False

if __name__=="__main__":
    m = HeadsetManager( dbus.SystemBus() )

