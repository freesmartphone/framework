#!/usr/bin/python -N
"""
framework tests

(C) 2008 Guillaume 'Charlie' Chereau <charlie@openmoko.org>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import unittest
import gobject
import threading
import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import test

class BaseTest(unittest.TestCase):
    def setUp(self):
        # We connect to the DBus object
        self.bus = dbus.SystemBus()
        self.preferences = self.bus.get_object('org.freesmartphone.opreferencesd', '/org/freesmartphone/Preferences')
    def test_profiles(self):
        """Test that we can get the profiles, and that we have a 'default' profile"""
        profiles = self.preferences.GetProfiles()
        assert 'default' in profiles
        assert 'silent' in profiles
        # Set the profile to default
        self.preferences.SetProfile('default')
        profile = self.preferences.GetProfile()
        assert profile == 'default'
        # Set the default profile to silent
        self.preferences.SetProfile('silent')
        profile = self.preferences.GetProfile()
        assert profile == 'silent'
    
    def test_services(self):
        """Try to get the 'profile' service"""
        services = self.preferences.GetServices()
        assert 'profiles' in services
        # Try to get a service that doesn't exist
        try:
            self.preferences.GetService('This_profile_does_not_exist')
        except dbus.DBusException, e:
            assert e._dbus_error_name == "org.freesmartphone.Preferences.NoServiceError", e._dbus_error_name
        else:
            assert False, "The error should be raised"
        # Now a valid one (profiles)
        path = self.preferences.GetService('profiles')
        assert(path == '/org/freesmartphone/Preferences/profiles')
    
    @test.taskletTest
    def test_get_key(self):
        """Try to get a valid key"""
        path = self.preferences.GetService('profiles')
        profiles = self.bus.get_object('org.freesmartphone.opreferencesd', path)
        profiles = dbus.Interface(profiles, 'org.freesmartphone.Preferences.Service')
        value = profiles.GetValue('profiles')
        yield True
    @test.taskletTest
    def test_get_invalid_key(self):
        """Try to get an invalid key"""
        path = self.preferences.GetService('profiles')
        profiles = self.bus.get_object('org.freesmartphone.opreferencesd', path)
        profiles = dbus.Interface(profiles, 'org.freesmartphone.Preferences.Service')
        self.assertRaises(dbus.exceptions.DBusException, profiles.GetValue, 'This_key_does_not_exist')
        yield True
    

if __name__ == '__main__':
    test.check_debug_mode()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BaseTest)
    result = unittest.TextTestRunner(verbosity=3).run(suite)
