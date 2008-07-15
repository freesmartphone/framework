#!/usr/bin/env python
"""
ogsmd tests

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

# Set those parameters to reflect the real conditions of the test
# TODO: make these command line options

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import gobject
import inspect
import thread
import time
import sys
from Queue import Queue
import types

verbose = True

# FIXME use OptionParser
config = dict( \
    SIM_PRESENT    = True,
    SIM_LOCKED     = True,
    SIM_PIN        = "6471",
    DIAL_NUMBER    = "+496968091892",
    )

class TE( Exception ):
    pass

queue = Queue()

#=========================================================================#
def signalHandler( data, member=None, destination=None, interface=None, path=None ):
#=========================================================================#
    """
    Signal handler that just puts the received signal with all its data into the queue
    """
    log( "got signal '%s.%s' with data", data )
    queue.put( member, data )

#=========================================================================#
def logged( fn ):
#=========================================================================#
    """
    Decorator that logs the name of a function each time it is called.
    If the function is a bound method, it also prints the classname.
    """
    def logIt( *args, **kwargs ):
        calldepth = len( inspect.stack() )-1
        try:
            classname = args[0].__class__.__name__
        except AttributeError:
            classname = ""
        print "%s> %s.%s: ENTER %s,%s" % ( '|...' * calldepth, classname, fn.__name__, repr(args[1:]), repr(kwargs) )
        result = fn( *args, **kwargs )
        print "%s> %s.%s: LEAVE" % ( '|...' * calldepth, classname, fn.__name__ )
        return result

    logIt.__dict__ = fn.__dict__
    logIt.__name__ = fn.__name__
    logIt.__doc__ = fn.__doc__
    return logIt


#=========================================================================#
def log( *args ):
#=========================================================================#
    """Only print if we are in verbose mode"""
    if verbose:
        for i in args:
            print prettyPrint( i ),
        if type( args[-1] ) == type( "" ) and args[-1].endswith( "..." ):
            pass
        else:
            print
            print
        sys.stdout.flush()


def prettyPrint( expression ):
    if type( expression ) == dbus.types.Array:
        result = [ "%s, " % prettyPrint(val) for val in expression ]
        return "[ %s ]" % result[:-2]
    elif type( expression ) == dbus.types.Dictionary:
        result = ""
        for key, val in expression.items():
            result += "\n    %s: %s" % ( prettyPrint(key), prettyPrint(val) )
        return "{ %s }" % result
    elif type( expression ) == dbus.types.String:
        return "'%s'" % expression
    else:
        return "%s" % expression

#=========================================================================#
class TestRunner( object ):
#=========================================================================#

    def __init__( self, failOnFirstFailed = True ):
        self.tests = []
        self.results = []

    def addTest( self, test, fatal = False ):
        test.fatal = fatal
        self.tests.append( test )

    def run( self ):
        # give mainloop a chance to set everything up
        time.sleep( 1 )
        for test in self.tests:
            kontinue = self.runTest( test )
            if not kontinue:
                print "TR: [FATAL FAIL]"
                break
        self.testEnds()

    def runTest( self, test ):
        print "="*78
        print "TR: [NEXT]", test.name, '\n'
        try:
            result = test.run()
        except Exception, e:
            print "ERROR during test:", e
            return self.testResult( test, False )
        else:
            return self.testResult( test, True )

    def testResult( self, test, result ):
        if result:
            print "TR: [PASS]", test.name
            self.results.append( ( test, "PASS" ) )
            return True
        else:
            print "TR: [FAIL]", test.name
            self.results.append( ( test, "FAIL" ) )
            return not test.fatal

    def testEnds( self ):
        # FIXME print summary
        print "TR: all tests done, quitting"
        mainloop.quit() # no more tests

#=========================================================================#
class AbstractTest( object ):
#=========================================================================#
    """
    An abstract test class
    """
    def __init__( self, counter = 1, name = None ):
        self.name = name or self.__class__.__name__

    def failWithDbusError( self, func, error ):
        try:
            func()
        except dbus.DBusException, e:
            if e.get_dbus_name() == error:
                log( "fails with", e.get_dbus_name(), "(OK)" )
            else:
                log( "fails with", e.get_dbus_name(), "(UNEXPECTED)" )
                raise AssertionError( "unexpected dbus error" )
        else:
            assert False, "%s did not fail. Expected was %s" % ( func, error )

#=========================================================================#
class DeviceAndAuthTest( AbstractTest ):
#=========================================================================#
    """
    org.freesmartphone.GSM.Device
     * GetInfo
     * GetFeatures
     * SetAntennaPower
     * NYI PrepareForSuspend()
     * NYI RecoverFromResume()

    org.freesmartphone.GSM.SIM
     * GetAuthStatus
     * SendAuthCode
     * GetSimInfo

    """
    serial = 0

    def run( self ):
        log( "get device info..." )
        info = device.GetInfo()
        log( "ok. info:", info )

        log( "get device features..." )
        features = device.GetFeatures()
        log( "ok. device features:", features )

        log( "antenna power off..." )
        device.SetAntennaPower( False )
        log( "ok" )

        log( "antenna power on..." )
        if config["SIM_LOCKED"]:
            self.failWithDbusError( lambda: device.SetAntennaPower( True ), "org.freesmartphone.GSM.SIM.AuthFailed" )

        log( "checking auth status..." )
        auth = sim.GetAuthStatus()

        if config["SIM_LOCKED"]:
            assert auth == "SIM PIN"
        else:
            assert auth == "READY"
        log( "ok. auth status is:", auth )

        if config["SIM_LOCKED"]:
            log( "sending unlock code..." )
            sim.SendAuthCode( config["SIM_PIN"] )
            log( "ok. auth status now:", sim.GetAuthStatus() )

        # FIXME we should have got an AuthChange signal in the meantime
        assert sim.GetAuthStatus() == "READY"

        log( "get sim info..." )
        info = sim.GetSimInfo()
        log( "ok. info:", info )

#=========================================================================#
class NetworkBaseTest( AbstractTest ):
#=========================================================================#
    """
    org.freesmartphone.GSM.Network

    * Unregister()
    * GetStatus()
    * Register()
    * ListProviders()
    * RegisterWithProvider()
    """
    serial = 1

    def run( self ):
        log( "unregistering..." )
        network.Unregister()
        log( "ok. checking status..." )
        status = network.GetStatus()
        assert status["registration"] == "unregistered"
        log( "ok. status now:", status )

        log( "autoregistering..." )
        network.Register()
        assert status["registration"] == "home"
        log( "ok. checking status..." )
        status = network.GetStatus()
        log( "ok. status now:", status )

        log( "checking available providers [will take some time]..." )
        providers = network.ListProviders( timeout = 1000 )
        log( "ok. provider list is:", providers

    # TODO pick a forbidden one, check whether registration is denied
    # TODO pick an allowed one, check whether registration is ok

#=========================================================================#
class CallBaseTest( AbstractTest ):
#=========================================================================#
    """
    org.freesmartphone.GSM.Call

    * Initiate()
    * Release()
    * HoldActive()
    * Activate()

    Testplan:
    * calling a number
    * check call status
    * cancel the call
    * check call status
    * call a number
    * check call status
    * wait for call to become active
    * check call status
    * hold call
    * check call status
    * activate call again
    * check call status
    * release call
    * check call status
    """
    serial = 1

    def run( self ):
        log( "calling", config["DIAL_NUMBER"], "..." )
        index = call.Initiate( config["DIAL_NUMBER"] )
        time.sleep( 1 )
        log( "ok. index =", index, ", checking call status..." )
        calls = call.GetCallStatus()
        log( "ok. calls:", calls )
        log( "waiting five seconds..." )
        time.sleep( 5 )
        call.Release( index )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    t = TestRunner()

    alltests = [ v for k, v in locals().items() if type(v) == types.TypeType and k.endswith( "Test" ) and k != "AbstractTest" ]
    alltests.sort( key=lambda element: element.serial )

    argv = sys.argv[1:]
    try:
        index = argv.index( "-t" )
    except ValueError:
        tests = alltests
    else:
        tests = eval( "[ %s ]" % argv[index+1] )

    for test in tests:
        t.addTest( test() )

    bus = dbus.SystemBus()
    try:
        device = sim = network = call = pdp = cb = bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
    except dbus.DBusException:
        print "ogsmd not present. could not launch tests."
        sys.exit( -1 )

    bus.add_signal_receiver(
        signalHandler,
        None,
        None,
        "org.freesmartphone.ogsmd",
        "/org/freesmartphone/GSM/Device",
        sender_keyword = "sender",
        destination_keyword = "destination",
        interface_keyword = "interface",
        member_keyword = "member",
        path_keyword = "path" )

    gobject.threads_init()

    thread.start_new_thread( t.run, () )

    mainloop = gobject.MainLoop()
    try:
        mainloop.run()
    except KeyboardInterrupt:
        mainloop.quit()
