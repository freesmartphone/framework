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
    _objectcache = {}
    _interfacecache = {}

    @classmethod
    def getInterface( klass, name, path, interface ):
        key = (name, path, interface)
        if not key in klass._interfacecache:
            obj = klass.getObject( name, path)
            klass._interfacecache[key] = dbus.Interface( obj, interface )
        return klass._interfacecache[key]

    @classmethod
    def getObject( klass, name, path ):
        key = (name, path)
        if not key in klass._objectcache:
            bus_pri = testloader.TestLoader.getInstance().primary_bus
            klass._objectcache[key] = bus_pri.get_object( name, path )
        return klass._objectcache[key]

    def setUp( self ):
        self.bus_pri = testloader.TestLoader.getInstance().primary_bus
        self.bus_sec = testloader.TestLoader.getInstance().secondary_bus

    def tearDown( self ):
        pass
