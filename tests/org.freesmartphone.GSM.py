#!/usr/bin/env python
"""
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

from test import request as REQUIRE
from test import testDbusValueIsInteger, \
                 testDbusDictionaryWithStringValues, \
                 testDbusDictionaryWithIntegerValues, \
                 testDbusType, \
                 taskletTest
import framework.patterns.tasklet as tasklet

import types, unittest, gobject, threading
import dbus, dbus.mainloop

dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )

SIM_PIN = "9797" # FIXME submit via configuration

SIGNAL_TIMEOUT_LOW = 5
SIGNAL_TIMEOUT_MID = 60
SIGNAL_TIMEOUT_HIGH = 60*5

#=========================================================================#
def testPhoneNumber( value ):
#=========================================================================#
    if value.startswith( '+' ):
        value = value[1:]
    for digit in value:
        assert digit in "0123456789", "wrong digit in phone number"

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
    def test_000_AntennaPower( self ):
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
    def test_001_AntennaPower( self ):
        """org.freesmartphone.GSM.Device.[Get|Set]AntennaPower"""

        self.device.SetAntennaPower(False)
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == False, "can't turn antenna power off"

        self.device.SetAntennaPower(True)
        result = self.device.GetAntennaPower()
        assert type( result ) is dbus.Boolean, "wrong type returned"
        assert result == True, "can't turn antenna power on"

    def test_002_GetInfo( self ):
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

    def test_003_GetFeatures( self ):
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

    # FIXME might add missing tests for
    #  * ChangeAuthCode
    #  * Unlock
    #  * SetAuthCodeRequired
    #  * GetAuthCodeRequired
    #  * SendGenericSimCommand
    #  * SendRestrictedSimCommand
    #  * GetHomeZones

    @REQUIRE( "sim.present", True )
    def test_010_ListPhonebooks( self ):
        """org.fresmartphone.GSM.SIM.ListPhonebooks"""

        result = self.sim.ListPhonebooks()
        assert type( result ) is dbus.Array, "wrong type returned"
        for value in result:
            assert type( value ) is dbus.String, "wrong type returned"

    @REQUIRE( "sim.present", True )
    def test_011_GetPhonebookInfo( self ):
        """org.freesmartphone.GSM.SIM.GetPhonebookInfo"""

        for phonebook in self.sim.ListPhonebooks():
            result = self.sim.GetPhonebookInfo( phonebook )
            assert type( result ) is dbus.Dictionary, "wrong type returned"
            for key in result.keys():
                assert type( key ) is dbus.String, "wrong type returned"
            for value in result.values():
                testDbusValueIsInteger( value )
            assert "min_index" in result, "mandatory entry missing"
            assert "max_index" in result, "mandatory entry missing"
            assert "name_length" in result, "mandatory entry missing"
            assert "number_length" in result, "mandatory entry missing"

    @REQUIRE( "sim.present", True )
    def test_010_RetrieveEntry( self ):
        """org.freesmartphone.GSM.SIM.RetrieveEntry"""

        for phonebook in self.sim.ListPhonebooks():
            info = self.sim.GetPhonebookInfo( phonebook )

            try:
                result = self.sim.RetrieveEntry( phonebook, info["min_index"]-1 ) # should fail
            except dbus.DBusException, e:
                assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.InvalidIndex", "wrong error returned"
            else:
                assert False, "InvalidIndex expected"

            try:
                result = self.sim.RetrieveEntry( phonebook, info["max_index"]+1 ) # should fail
            except dbus.DBusException, e:
                assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.InvalidIndex", "wrong error returned"
            else:
                assert False, "InvalidIndex expected"

            result = self.sim.RetrieveEntry( phonebook, info["min_index"] )
            assert type( result ) == types.TupleType, "wrong type returned"
            assert len( result ) == 2, "wrong length for struct"
            assert type( result[0] ) == dbus.String, "type for name not string"
            assert type( result[1] ) == dbus.String, "type for number not string"

            result = self.sim.RetrieveEntry( phonebook, info["max_index"] )
            assert type( result ) == types.TupleType, "wrong type returned"
            assert len( result ) == 2, "wrong length for struct"
            assert type( result[0] ) == dbus.String, "type for name not string"
            assert type( result[1] ) == dbus.String, "type for number not string"

    @REQUIRE( "sim.present", True )
    def test_011_StoreEntry( self ):
        """org.freesmartphone.GSM.SIM.StoreEntry (national)"""

        try:
            index = self.sim.GetPhonebookInfo( "contacts" )["max_index"]
        except dbus.DBusException:
            return

        self.sim.StoreEntry( "contacts", index, "Dr. med. Wurst", "123456789" )

        newname, newnumber = self.sim.RetrieveEntry( "contacts", index )
        assert newname == "Dr. med. Wurst" and newnumber == "123456789", "could not store entry on SIM"

    #
    # FIXME what should happen if we give an empty name and/or number?
    #

    @REQUIRE( "sim.present", True )
    def test_012_StoreEntry( self ):
        """org.freesmartphone.GSM.SIM.StoreEntry (international)"""

        try:
            index = self.sim.GetPhonebookInfo( "contacts" )["max_index"]
        except dbus.DBusException:
            return

        self.sim.StoreEntry( "contacts", index, "Dr. med. Wurst", "+49123456789" )
        newname, newnumber = self.sim.RetrieveEntry( "contacts", index )
        assert newname == "Dr. med. Wurst" and newnumber == "+49123456789", "could not store entry on SIM"

    @REQUIRE( "sim.present", True )
    def test_013_DeleteEntry( self ):
        """org.freesmartphone.GSM.SIM.DeleteEntry"""

        try:
            index = self.sim.GetPhonebookInfo( "contacts" )["max_index"]
        except dbus.DBusException:
            return
        self.sim.DeleteEntry( "contacts", index )

    #
    # FIXME add message book testing
    #

    @REQUIRE( "sim.present", True )
    def test_020_GetServiceCenterNumber( self ):
        """org.freesmartphone.GSM.SIM.GetServiceCenterNumber"""

        result = self.sim.GetServiceCenterNumber()
        assert type( result ) == dbus.String, "expected a string"
        testPhoneNumber( result )

    @REQUIRE( "sim.present", True )
    def test_021_SetServiceCenterNumber( self ):
        """org.freesmartphone.GSM.SIM.SetServiceCenterNumber"""

        NEW = "+49123456789"

        old = self.sim.GetServiceCenterNumber()
        new = self.sim.SetServiceCenterNumber( NEW )
        assert self.sim.GetServiceCenterNumber() == NEW, "can't change SMS service center number"
        self.sim.SetServiceCenterNumber( old )

#=========================================================================#
class GsmNetworkTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.Network.*"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
        self.device = dbus.Interface( obj, "org.freesmartphone.GSM.Device" )
        self.sim = dbus.Interface( obj, "org.freesmartphone.GSM.SIM" )
        self.network = dbus.Interface( obj, "org.freesmartphone.GSM.Network" )

    def tearDown( self ):
        pass

    '''

    @REQUIRE( "sim.present", True )
    def test_000_Register( self ):
        """org.freesmartphone.GSM.Network.Register"""

        self.device.SetAntennaPower( False )
        try:
            self.device.SetAntennaPower( True )
        except dbus.DBusException, e:
            self.sim.SendAuthCode( SIM_PIN )

        self.network.Register()

    @REQUIRE( "sim.present", False )
    def test_001_Register( self ):
        """org.freesmartphone.GSM.Network.Register"""

        self.device.SetAntennaPower( False )
        self.device.SetAntennaPower( True )
        try:
            self.network.Register()
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.Network.EmergencyOnly"

    @REQUIRE( "sim.present", True )
    def test_002_GetStatus( self ):
        """org.freesmartphone.GSM.Network.GetStatus (unregistered)"""

        self.network.Unregister()
        result = self.network.GetStatus()
        assert type( result ) == dbus.Dictionary, "dictionary expected"
        assert "registration" in result, "mandatory 'registration' tuple missing"
        assert result["registration"] == "unregistered", "expected registration = 'unregistered', got '%s' instead" % result["registration"]
        assert "mode" in result, "mandatory 'mode' tuple missing"
        assert result["mode"] == "unregister"

        for key in result:
            assert key in "registration mode provider code strength lac cid".split(), "unexpected key '%s'" % key

    @REQUIRE( "sim.present", True )
    def test_003_GetStatus( self ):
        """org.freesmartphone.GSM.Network.GetStatus (registered)"""

        self.network.Register()
        result = self.network.GetStatus()
        assert type( result ) == dbus.Dictionary, "dictionary expected"
        assert "registration" in result, "mandatory 'registration' tuple missing"
        assert result["registration"] == "home", "expected registration = 'home', got '%s' instead" % result["registration"]
        assert "mode" in result, "mandatory 'mode' tuple missing"
        assert result["mode"] == "automatic"

        for key in result:
            assert key in "registration mode provider code strength lac cid".split(), "unexpected key '%s'" % key

    def test_004_GetSignalStrength( self ):
        """org.freesmartphone.GSM.Network.GetSignalStrength"""

        result = self.network.GetSignalStrength()
        testDbusValueIsInteger( result )
        assert 0 <= result <= 100, "signal strength value out of bounds"

    @REQUIRE( "sim.present", True )
    @taskletTest
    def test_005_Status( self ):
        """org.freesmartphone.GSM.Network.Status (unregistered)"""

        self.network.Register()
        self.network.Unregister( reply_handler=lambda:None, error_handler=lambda Foo:None )

        result = yield ( tasklet.WaitDBusSignal( self.network, 'Status', SIGNAL_TIMEOUT_MID ) )
        assert type( result ) == dbus.Dictionary, "dictionary expected"
        assert "registration" in result, "mandatory 'registration' tuple missing"
        assert result["registration"] in "unregistered home busy denied unknown roaming".split(), "unexpected setting for registration"
        assert "mode" in result, "mandatory 'mode' tuple missing"
        assert result["mode"] == "unregister"

        for key in result:
            assert key in "registration mode provider code strength lac cid".split(), "unexpected key '%s'" % key

        assert result["registration"] == "unregistered"

    @REQUIRE( "sim.present", True )
    @taskletTest
    def test_006_Status( self ):
        """org.freesmartphone.GSM.Network.Status (home)"""

        self.network.Unregister()
        self.network.Register( reply_handler=lambda:None, error_handler=lambda Foo:None )

        result = yield ( tasklet.WaitDBusSignal( self.network, 'Status', SIGNAL_TIMEOUT_MID ) )
        assert result["registration"] == "home"

    @REQUIRE( "sim.present", True )
    def test_010_ListOperators( self ):
        """org.freesmartphone.GSM.ListProviders"""

        self.network.Register()
        result = self.network.ListProviders( timeout=60000 )
        assert type( result ) == dbus.Array, "array expected, got '%s' instead" % type( result )
        for value in result:
            testDbusType( value, dbus.Struct )
            assert len( value ) == 4, "expected a 4-tuple, got a %d-tuple" % len( value )
            code, status, longname, shortname = value
            testDbusValueIsInteger( code )
            testDbusType( status, dbus.String )
            testDbusType( longname, dbus.String )
            testDbusType( shortname, dbus.String )
            assert status in "forbidden current home".split(), "unexpected status '%s', valid are 'forbidden', 'current', 'home'" % status

    '''
    @REQUIRE( "sim.present", True )
    def test_011_RegisterWithProvider( self ):
        """org.freesmartphone.GSM.RegisterWithProvider"""

        result = self.network.ListProviders( timeout=60000 )
        for code, status, longname, shortname in result:
            if status == "forbidden":
                try:
                    self.network.RegisterWithProvider( code )
                except dbus.DBusException, e:
                    assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.Blocked", "unexpected error"
                else:
                    assert False, "expected error SIM.Blocked"
                break

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suites = []
    #suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmDeviceTest ) )
    #suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmSimTest ) )
    suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmNetworkTest ) )
    # FIXME this is not conform with unit tests, but for now we only test this file anyways
    # will fix later
    for suite in suites:
        result = unittest.TextTestRunner( verbosity=3 ).run( suite )
