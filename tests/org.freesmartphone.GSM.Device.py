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

    def test_000_AntennaPower( self ):
        """org.freesmartphone.GSM.Device.[Get|Set]AntennaPower"""

        self.interface.SetAntennaPower(False)
        result = self.interface.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == False, "can't turn antenna power off"

        self.interface.SetAntennaPower(True)
        result = self.interface.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == True, "can't turn antenna power on"

    def test_001_GetInfo( self ):
        """org.freesmartphone.GSM.Device.GetInfo"""

        result = self.interface.GetInfo()
        assert type( result ) is dbus.Dictionary, "wrong type returned"
        for key in result.keys():
            assert type( key ) is dbus.String, "wrong type returned"
        for value in result.values():
            assert type( value ) is dbus.String, "wrong type returned"
        assert "manufacturer" in result, "mandatory entry missing"
        assert "imei" in result, "mandatory entry missing"
        assert len( result["imei"] ) == 15, "wrong length for IMEI"

    def test_002_GetFeatures( self ):
        """org.freesmartphone.GSM.Device.GetFeatures"""

        result = self.interface.GetFeatures()
        assert type( result ) is dbus.Dictionary, "wrong type returned"
        for key in result.keys():
            assert type( key ) is dbus.String, "wrong type returned"
        for value in result.values():
            assert type( value ) is dbus.String, "wrong type returned"
        assert "GSM" in result, "mandatory entry missing"

    def test_003_SimBuffersSMS( self ):
        """org.freesmartphone.GSM.Device.[Get|Set]SimBuffersSms"""
        result = self.interface.GetSimBuffersSms()

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suite = unittest.defaultTestLoader.loadTestsFromTestCase( GsmDeviceTest )
    result = unittest.TextTestRunner( verbosity=3 ).run( suite )
