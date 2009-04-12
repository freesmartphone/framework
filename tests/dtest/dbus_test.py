#!/usr/bin/env python
"""
FSO DBus API high level Testsuite

(C) 2009 Daniel Willmann <daniel@totalueberwachung.de>
GPLv2 or later
"""

import dbus, glib, gobject
import sys, os, optparse, time
import subprocess, signal

class MyOptionParser( optparse.OptionParser ):
    def __init__( self ):
        optparse.OptionParser.__init__( self )
        self.add_option( "-t", "--tests",
            dest = "tests",
            help = "Tests to run (all)",
            metavar = "test1,test2,test3",
            action = "store"
        )
        self.add_option( "-p", "--primary",
            metavar = "IP",
            dest = "primary",
            help = "IP of the primary phone (for gabriel)",
            action = "store",
        )
        self.add_option( "-s", "--secondary",
            metavar = "IP",
            dest = "seconary",
            help = "IP of the secondary phone (for gabriel)",
            action = "store",
        )

if __name__ == "__main__":
    options = MyOptionParser()
    options.parse_args( sys.argv )

    GABRIEL_CONNECT = lambda x,y: ( "gabriel", "--host=%s"%(x), "--username=root", "--password=", "-d","unix:path=/var/run/dbus/system_bus_socket", "-b", y )

    # Start gabriel to the devices
    gabriel_pri = subprocess.Popen(GABRIEL_CONNECT(options.values.primary, "primary"))
    if options.values.secondary == "":
        gabriel_sec = subprocess.Popen(GABRIEL_CONNECT(options.values.secondary, "secondary"))
    else:
        gabriel_sec = None

    time.sleep(2)

    error = gabriel_pri.poll()
    if not error == None:
        print "WARNING: Gabriel exited with errorcode %i"%(error)
        print "Aborting"
        sys.exit(1)

    os.environ['DBUS_SESSION_BUS_ADDRESS'] = "unix:abstract=primary"
    bus_pri = dbus.bus.BusConnection( dbus.bus.BUS_SESSION )

    if not gabriel_sec == None:
        error = gabriel_sec.poll()
        if not error == None:
            print "WARNING: Gabriel exited with errorcode %i"%(error)
            print "Aborting"
            sys.exit(1)
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = "unix:abstract=secondary"
        bus_sec = dbus.bus.BusConnection( dbus.bus.BUS_SESSION )


    # Some static tests for now
    test = bus_pri.get_object( 'org.freesmartphone.ousaged', '/org/freesmartphone/Usage' )
    testiface = dbus.Interface( test, 'org.freesmartphone.Usage' )

    print testiface.ListResources()
    testiface.SetResourcePolicy("Display", "enabled")
    testiface.SetResourcePolicy("Display", "auto")

    # This only works for python >2.6
    #gabriel_pri.kill()
    # XXX: Why doesn't TERM work here?!
    os.kill( gabriel_pri.pid, signal.SIGKILL )
