"""
FSO DBus API high level Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later

Test Usage interface
"""

import unittest
import fsotest, dbus


class UsageTest(fsotest.FSOTestCase):
    def setUp( self ):
        fsotest.FSOTestCase.setUp( self )
        self.usage = fsotest.FSOTestCase.getInterface( 'org.freesmartphone.ousaged', '/org/freesmartphone/Usage', 'org.freesmartphone.Usage' )

    def test_usagelist( self ):
        """ Try to get the resource list """
        result = self.usage.ListResources()
    def test_requestrelease( self ):
        """ Request/Release resource and check state """
        reslist = self.usage.ListResources()
        self.assert_("TEST" in reslist)
        resusr = self.usage.GetResourceUsers("TEST")
        self.usage.RequestResource("TEST")
        self.assertEquals(len(resusr)+1, len(self.usage.GetResourceUsers("TEST")))

	self.assertRaises(dbus.DBusException, self.usage.RequestResource, "TEST" )

        self.assertEquals(len(resusr)+1, len(self.usage.GetResourceUsers("TEST")))
        self.usage.ReleaseResource("TEST")
        self.assertEquals(len(resusr), len(self.usage.GetResourceUsers("TEST")))
    def test_policychange( self ):
        """ Change the resource policy and check """
        pass

