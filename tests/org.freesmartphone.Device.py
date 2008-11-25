#!/usr/bin/env python
"""
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

from test import request as REQUIRE
import framework.patterns.tasklet as tasklet

import unittest
import gobject
import threading
import dbus, dbus.mainloop

dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )

SOUND_RESOURCE = "/usr/share/sounds/Arkanoid_PSID.sid"

#=========================================================================#
class DeviceAudioTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.Device.*"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/Audio" )
        self.audio = dbus.Interface( obj, "org.freesmartphone.Device.Audio" )

    def tearDown( self ):
        pass

    #
    # Tests
    #

    def test_000_PlaySound( self ):
        """org.freesmartphone.Device.Audio.PlaySound"""

        try:
            self.audio.PlaySound( "/this/resource/hopefully/not/there.wav", 0, 0 )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.Device.Audio.PlayerError", "wrong error returned"
        else:
            assert False, "PlayerError expected"

        try:
            self.audio.PlaySound( "/this/resource/hopefully/not/there.unknownFormat", 0, 0 )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.Device.Audio.UnknownFormat", "wrong error returned"
        else:
            assert False, "UnknownFormat expected"

        self.audio.PlaySound( SOUND_RESOURCE, 0, 0 )

        try:
            self.audio.PlaySound( SOUND_RESOURCE, 0, 0 )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.Device.Audio.AlreadyPlaying", "wrong error returned"
        else:
            assert False, "AlreadyPlaying expected"

    def test_001_StopSound( self ):
        """org.freesmartphone.Device.Audio.StopSound"""

        try:
            self.audio.StopSound( "/this/resource/not.there" )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.Device.Audio.NotPlaying", "wrong error returned"
        else:
            assert False, "NotPlaying expected"

        self.audio.StopSound( SOUND_RESOURCE )

    def test_002_StopAllSounds( self ):
        """org.freesmartphone.Device.Audio.StopSound"""

        self.audio.StopAllSounds()

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suites = []
    suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( DeviceAudioTest ) )
    # suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmSimTest ) )
    # FIXME this is not conform with unit tests, but for now we only test this file anyways
    # will fix later
    for suite in suites:
        result = unittest.TextTestRunner( verbosity=3 ).run( suite )
