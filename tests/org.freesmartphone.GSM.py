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
                 testDbusError, \
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
        assert digit in "0123456789", "wrong digit '%s' in phone number '%s'" % ( digit, value )

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
        testDbusType( result, dbus.Array )
        for value in result:
            testDbusType( value, dbus.String )

    @REQUIRE( "sim.present", True )
    def test_011_RetrievePhonebook( self ):
        """org.fresmartphone.GSM.SIM.RetrievePhonebook"""

        try:
            self.sim.RetrievePhonebook( "this/phonebook/not/there" )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.InvalidParameter"
        else:
            assert False, "InvalidParameter expected"

        for phonebook in self.sim.ListPhonebooks():
            result = self.sim.RetrievePhonebook( phonebook )
            testDbusType( result, dbus.Array )

            for entry in result:
                testDbusType( entry, dbus.Struct )
                assert len( entry ) == 3, "wrong length for struct"
                testDbusValueIsInteger( entry[0] )
                assert type( entry[1] ) == dbus.String, "type for name not string"
                assert type( entry[2] ) == dbus.String, "type for number not string"

    @REQUIRE( "sim.present", True )
    def test_012_GetPhonebookInfo( self ):
        """org.freesmartphone.GSM.SIM.GetPhonebookInfo"""

        try:
            self.sim.GetPhonebookInfo( "this/phonebook/not/there" )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.InvalidParameter"
        else:
            assert False, "InvalidParameter expected"

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
    def test_013_RetrieveEntry( self ):
        """org.freesmartphone.GSM.SIM.RetrieveEntry"""

        try:
            self.sim.RetrieveEntry( "this/phonebook/not/there", 1 ) # should faile
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.InvalidParameter"
        else:
            assert False, "InvalidParameter expected"

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
    def test_014_StoreEntry( self ):
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

    @REQUIRE( "sim.present", True )
    def test_031_GetMessageBookInfo( self ):
        """org.freesmartphone.GSM.SIM.GetMessagebookInfo"""

        result = self.sim.GetMessagebookInfo()
        testDbusType( result, dbus.Dictionary )
        for key, value in result.items():
            assert key in "first last used".split()
            testDbusValueIsInteger( value )

    @REQUIRE( "sim.present", True )
    def test_032_RetrieveMessageBook( self ):
        """org.freesmartphone.GSM.SIM.RetrieveMessagebook"""

        try:
            index = self.sim.RetrieveMessagebook( "this_no_messagebook" )
        except dbus.DBusException, e:
            assert e.get_dbus_name() == "org.freesmartphone.GSM.InvalidParameter", "wrong error returned"
        else:
            assert False, "expected InvalidParameter"

        result = self.sim.RetrieveMessagebook( "all" )
        testDbusType( result, dbus.Array )
        for entry in result:
            testDbusType( entry, dbus.Struct )
            assert len( entry ) == 5, "expected 5 elements for one entry"
            index, category, peer, contents, properties = entry
            testDbusValueIsInteger( index )
            assert category in "read unread sent unsent".split(), "unexpected category '%s', valid are 'read unread sent unsent'" % category
            testDbusType( peer, dbus.String ) # can be number or name (if found on SIM)
            testDbusType( contents, dbus.String )
            testDbusType( properties, dbus.Dictionary )

        for category in "read unread sent unsent".split():
            result = self.sim.RetrieveMessagebook( category )
            for entry in result:
                index, cat, number, contents, properties = entry
                assert cat == category, "expected category '%s', got '%s'" % ( category, cat )

    @REQUIRE( "sim.present", True )
    def test_033_RetrieveMessage( self ):
        """org.freesmartphone.GSM.SIM.RetrieveMessage"""

        for index in xrange( 1, 255 ):
            try:
                entry = self.sim.RetrieveMessage( index )
            except dbus.DBusException, e:
                assert e.get_dbus_name() == "org.freesmartphone.GSM.SIM.NotFound", "unexpected error returned"
            else:
                testDbusType( entry, types.TupleType )
                assert len( entry ) == 4, "expected 4 elements for one entry"
                category, peer, contents, properties = entry
                assert category in "read unread sent unsent".split(), "unexpected category '%s', valid are 'read unread sent unsent'" % category
                testDbusType( peer, dbus.String ) # can be number or name (if found on SIM)
                testDbusType( contents, dbus.String )
                testDbusType( properties, dbus.Dictionary )

    # FIXME add missing tests for:
    # * StoreMessage
    # * SendStoredMessage

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
        """org.freesmartphone.GSM.Network.ListProviders"""

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

    @REQUIRE( "sim.present", True )
    def test_011_RegisterWithProvider( self ):
        """org.freesmartphone.GSM.Network.RegisterWithProvider"""

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

    @REQUIRE( "sim.present", True )
    def test_012_GetNetworkCountryCode( self ):
        """org.freesmartphone.GSM.Network.GetNetworkCountryCode"""

        self.network.Unregister()
        try:
            self.network.GetNetworkCountryCode()
        except dbus.DBusException, e:
            testDbusError( e, "org.freesmartphone.GSM.Network.NotFound" )
        else:
            assert False, "expected Network.NotFound"

        self.network.Register()
        result = self.network.GetNetworkCountryCode()
        testDbusType( result, types.TupleType )
        assert len( result ) == 2, "expected 2 parameters, got %d" % len( result )
        testPhoneNumber( result[0] )
        testDbusType( result[1], dbus.String )

    # FIXME: add missing tests for
    # * GetCallForwarding
    # * EnableCallForwarding
    # * DisableCallForwarding

    @REQUIRE( "sim.present", True )
    def test_030_GetCallingIdentification( self ):
        """org.freesmartphone.GSM.Network.GetCallingIdentification"""

        result = self.network.GetCallingIdentification()
        testDbusType( result, dbus.String )
        assert result in "on off network".split()

    @REQUIRE( "sim.present", True )
    def test_031_SetCallingIdentification( self ):
        """org.freesmartphone.GSM.Network.SetCallingIdentification"""

        try:
            self.network.SetCallingIdentification( "this not valid" )
        except dbus.DBusException, e:
            testDbusError( e, "org.freesmartphone.GSM.InvalidParameter" )
        else:
            assert False, "expected InvalidParameter"

        old = self.network.GetCallingIdentification()
        self.network.SetCallingIdentification( old )

    # * SendUssdRequest
    # * ... signals ...

#=========================================================================#
class GsmCbTest( unittest.TestCase ):
#=========================================================================#
    """Tests for org.freesmartphone.GSM.CB.*"""

    def setUp(self):
        self.bus = dbus.SystemBus()
        obj = self.bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
        self.device = dbus.Interface( obj, "org.freesmartphone.GSM.Device" )
        self.sim = dbus.Interface( obj, "org.freesmartphone.GSM.SIM" )
        self.network = dbus.Interface( obj, "org.freesmartphone.GSM.Network" )
        self.cb = dbus.Interface( obj, "org.freesmartphone.GSM.CB" )

    def tearDown( self ):
        pass

    @REQUIRE( "sim.present", True )
    def test_000_GetCellBroadcastSubscription( self ):
        """org.freesmartphone.GSM.Network.GetCellBroadcastSubscriptions"""

        result = self.cb.GetCellBroadcastSubscriptions()
        testDbusType( result, dbus.String )

    @REQUIRE( "sim.present", True )
    def test_000_GetCellBroadcastSubscriptions( self ):
        """org.freesmartphone.GSM.Network.GetCellBroadcastSubscriptions"""

        self.cb.SetCellBroadcastSubscriptions( "all" )
        self.cb.SetCellBroadcastSubscriptions( "221" )
        self.cb.SetCellBroadcastSubscriptions( "none" )
        assert self.cb.GetCellBroadcastSubscriptions() == "none", "can't set cell broadcast subscriptions"

    # FIXME unfortunately we can't test incoming cell broadcast subscriptions without a simulated modem

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    suites = []
    #suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmDeviceTest ) )
    #suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmSimTest ) )
    #suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmNetworkTest ) )
    suites.append( unittest.defaultTestLoader.loadTestsFromTestCase( GsmCbTest ) )
    # FIXME this is not conform with unit tests, but for now we only test this file anyways
    # will fix later
    for suite in suites:
        result = unittest.TextTestRunner( verbosity=3 ).run( suite )
