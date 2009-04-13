"""
FSO DBus API high level Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later

unittest.TestCase with convenience functions for FSO testing
"""

import unittest
import dbus
import testloader

class FSOTestCase(unittest.TestCase):
    def setUp( self ):
        self.bus_pri = testloader.TestLoader.getInstance().primary_bus
        self.bus_sec = testloader.TestLoader.getInstance().secondary_bus

    def tearDown( self ):
        pass

