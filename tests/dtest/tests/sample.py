"""
FSO DBus API high level Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later

Sample testing file
"""

import unittest
import fsotest, dbus


class SampleTest(fsotest.FSOTestCase):
    def test_foo( self ):
        """ Dummy test always succeeds """
	return

    def test_usage( self ):
        """ Try to get the resource list """
        test = self.bus_pri.get_object( 'org.freesmartphone.ousaged', '/org/freesmartphone/Usage' )
        testiface = dbus.Interface( test, 'org.freesmartphone.Usage' )
        result = testiface.ListResources()
