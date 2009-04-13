"""
FSO DBus API high level Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later

Testloader to add and run the tests
"""

import unittest
import sys, os

class TestLoader(object):
    _instance = None

    @classmethod
    def getInstance( klass, tests = None, bus_pri = None, bus_sec = None ):
        if klass._instance is None:
            klass._instance = TestLoader( tests, bus_pri, bus_sec )
        return klass._instance

    def __init__( self, tests, bus_pri, bus_sec ):
        self.tests = tests
        self.primary_bus = bus_pri
        self.secondary_bus = bus_sec
        self.suite = unittest.TestSuite()
	sys.path.append( os.path.dirname( os.path.abspath( os.path.curdir )))

        if self.tests is None:
            self.tests = self.findAllTestFiles()
        else:
            self.tests = self.tests.split(",")

        for test in self.tests:
            self.addTestCasesInFile( test )

    def findAllTestFiles( self ):
        tests = os.listdir("tests/")
	tests = [ test[:-3] for test in tests if test.endswith(".py") ]
	return tests

    def addTestCasesInFile( self, file ):
        name = "tests.%s"%(file)
        try:
            __import__( name )
            module = sys.modules[name]
            self.suite.addTest( unittest.defaultTestLoader.loadTestsFromModule(module) )
        except Exception, e:
            print "Error processing test %s" % ( file )
            print e

    def runTests( self ):
        unittest.TextTestRunner(verbosity=2).run(self.suite)
