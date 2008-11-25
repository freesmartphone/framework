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

SIM_PIN = "9797" # FIXME submit via configuration

#=========================================================================#
class GsmDeviceTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.Device.*"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
        self.device = dbus.Interface( obj, "org.freesmartphone.GSM.Device" )

    def tearDown( self ):
        pass

    #
    # Tests
    #

    @REQUIRE( ( "sim.present", True ), ( "sim.locked", True ) )
    def test_000_AntennaPower_A( self ):
        """org.freesmartphone.GSM.Device.[Get|Set]AntennaPower"""

        self.device.SetAntennaPower(False)
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == False, "can't turn antenna power off"

        # only SOME modems can't do that, so don't rely on the exception
        try:
            self.device.SetAntennaPower(True)
        except dbus.DBusException:
            pass
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == True, "can't turn antenna power on"

    @REQUIRE( ( "sim.present", True ), ( "sim.locked", False ) )
    def test_000_AntennaPower_B( self ):
        """org.freesmartphone.GSM.Device.[Get|Set]AntennaPower"""

        self.device.SetAntennaPower(False)
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == False, "can't turn antenna power off"

        self.device.SetAntennaPower(True)
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == True, "can't turn antenna power on"

    def test_001_GetInfo( self ):
        """org.freesmartphone.GSM.Device.GetInfo"""

        result = self.device.GetInfo()
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

        result = self.device.GetFeatures()
        assert type( result ) is dbus.Dictionary, "wrong type returned"
        for key in result.keys():
            assert type( key ) is dbus.String, "wrong type returned"
        for value in result.values():
            assert type( value ) is dbus.String, "wrong type returned"
        assert "GSM" in result, "mandatory entry missing"

    # NOTE: Missing here is [Get|Set]SimBuffersSms -- this needs an
    # unlocked SIM and an operator -- hence is part of a higher level test
    # in GsmSmsTest

#=========================================================================#
class GsmSimTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.SIM.*"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
        self.device = dbus.Interface( obj, "org.freesmartphone.GSM.Device" )
        self.sim = dbus.Interface( obj, "org.freesmartphone.GSM.SIM" )

    def tearDown( self ):
        pass

    #
    # Tests
    #

    @REQUIRE( "sim.present", True )
    def test_001_GetSimInfo( self ):
        """org.freesmartphone.GSM.SIM.GetSimInfo"""

        # some modems allow that, some not
        try:
            result = self.sim.GetSimInfo()
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.AuthFailed", "wrong error returned"
        else:
            assert type( result ) is dbus.Dictionary, "wrong type returned"
            for key in result.keys():
                assert type( key ) is dbus.String, "wrong type returned"
            assert "imsi" in result, "mandatory entry missing"
            assert len( result["imsi"] ) == 15, "wrong length for IMSI"
            # FIXME check optional arguments

    @REQUIRE( "sim.present", False )
    def test_002_GetSimInfo( self ):
        """org.freesmartphone.GSM.SIM.GetSimInfo"""

        # FIXME check whether we get the correct exception

    @REQUIRE( ( "sim.present", True ), ( "sim.locked", True ) )
    def test_003_GetAuthStatus( self ):
        """org.freesmartphone.GSM.SIM.AuthStatus"""

        # power-cycle, so we reset the PIN
        self.device.SetAntennaPower( False )
        # some modems return CMS ERROR here, some not :/
        try:
            self.device.SetAntennaPower( True )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.AuthFailed", "wrong error returned"
        else:
            pass

        result = self.sim.GetAuthCode()
        assert type( result ) == dbus.String, "wrong type returned"
        assert result == "SIM PIN", "unexpected auth code"

    @REQUIRE( ( "sim.present", True ), ( "sim.locked", False ) )
    def test_004_GetAuthStatus( self ):
        """org.freesmartphone.GSM.SIM.AuthStatus"""

        # power-cycle, so we reset the PIN
        self.device.SetAntennaPower( False )
        self.device.SetAntennaPower( True )

        result = self.sim.GetAuthCode()
        assert type( result ) == dbus.String, "wrong type returned"
        assert result == "READY", "unexpected auth code"

    @REQUIRE( ( "sim.present", True ), ( "sim.locked", True ) )
    def test_005_SendAuthCode( self ):
        """org.freesmartphone.GSM.SIM.SendAuthCode"""

        # power-cycle, so we reset the PIN
        self.device.SetAntennaPower( False )
        try:
            self.device.SetAntennaPower( True )
        except dbus.DBusException:
            pass

        try:
            self.sim.SendAuthCode( "WRONG" )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.AuthFailed", "wrong error returned"

        self.sim.SendAuthCode( SIM_PIN )
        assert self.sim.GetAuthCode() == "READY", "can't unlock SIM"

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suites = []
    suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmDeviceTest ) )
    # suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmSimTest ) )
    # FIXME this is not conform with unit tests, but for now we only test this file anyways
    # will fix later
    for suite in suites:
        result = unittest.TextTestRunner( verbosity=3 ).run( suite )
