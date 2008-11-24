#!/usr/bin/env python
"""
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

import test
import framework.patterns.tasklet as tasklet

import unittest
import gobject
import threading
import dbus, dbus.mainloop

dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )

#=========================================================================#
class GsmDeviceTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.Device"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        #self.usage = self.bus.get_object('org.freesmartphone.ousaged', '/org/freesmartphone/Usage')
        #self.usage = dbus.Interface(self.usage, 'org.freesmartphone.Usage')
        # Get the gsm interface
        gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
        self.interface = dbus.Interface(gsm, 'org.freesmartphone.GSM.Device')

        #self.usage.RequestResource('GSM')

    def tearDown( self ):
        pass
        #self.usage.ReleaseResource('GSM')

    def test_GetInfo( self ):
        """org.freesmartphone.GSM.Device.GetInfo"""
        info = self.interface.GetInfo()
        assert type( info ) is dbus.Dictionary, "wrong type returned"
        for result in info.values():
            assert type( result ) is dbus.String, "wrong type returned"
        assert "manufacturer" in info, "mandatory entry missing"
        assert "imei" in info, "mandatory entry missing"
        assert len( info["imei"] ) == 15, "wrong length for IMEI"

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suite = unittest.defaultTestLoader.loadTestsFromTestCase( GsmDeviceTest )
    result = unittest.TextTestRunner( verbosity=3 ).run( suite )
