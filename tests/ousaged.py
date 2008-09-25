#!/usr/bin/env python
"""
Open Device Daemon - Controller

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import gobject
import threading
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import time
import framework

from tasklet import Tasklet, WaitDBusSignal, WaitDBus

verbose = True

def dbus_to_python(v):
    """This function convert a dbus object to a python object"""
    if isinstance(v, dbus.Int32):
        return int(v)
    if isinstance(v, dbus.String):
        return str(v)
    if isinstance(v, dbus.Dictionary):
        return dict( (dbus_to_python(k), dbus_to_python(v)) for k,v in v.iteritems() )
    if isinstance(v, dbus.Array):
        return [dbus_to_python(x) for x in v]
    if isinstance(v, dbus.Struct):
        return tuple(dbus_to_python(x) for x in v)
    print "Can't convert type %s" % type(v)
    return v

def vprint(msg, *args):
    """Only print if we are in verbose mode"""
    if verbose:
        print msg % args

class Test(Tasklet):
    def run(self):
        """This is the main task of the Test class.
           It runs in a tasklet, so I can use yield to block without using thread
        """
        print "== Connect to dbus services =="
        self.bus = dbus.SystemBus()
        self.usage = self.bus.get_object('org.freesmartphone.ousaged', '/org/freesmartphone/Usage')
        print "OK"

        yield self.test_client_resource()


    def test_client_resource(self):
        print "== Test client resource =="
        class ClientResource( dbus.service.Object ):
            ## This is our test client resource object
            def __init__(self):
                bus = dbus.SystemBus()
                dbus.service.Object.__init__( self, bus, '/org/freesmatrphone/Test' )
                self.enabled = False
            
            @dbus.service.method( 'org.freesmartphone.Resource', "", "" )
            def Enable( self ):
                print "Enable"
                assert not self.enabled
                self.enabled = True
            
            @dbus.service.method( 'org.freesmartphone.Resource', "", "" )
            def Disable( self ):
                print "Disable"
                assert self.enabled
                self.enabled = False
                
            @dbus.service.method( 'org.freesmartphone.Resource', "", "" )
            def Suspend( self ):
                print "Suspend"
                
            @dbus.service.method( 'org.freesmartphone.Resource', "", "" )
            def Resume( self ):
                print "Resumed"
                
        # Create and register the 'test' resource
        resource = ClientResource()
        self.usage.RegisterResource( 'test', resource )
        # request the resource (twice)
        yield WaitDBus( self.usage.RequestResource, 'test' )
        yield WaitDBus( self.usage.RequestResource, 'test' )
        # release the resource (twice)
        yield WaitDBus( self.usage.ReleaseResource, 'test' )
        yield WaitDBus( self.usage.ReleaseResource, 'test' )
        
        # Suspend the system
        # Warning : if we run this test via ssh over USB,
        # then we are going to lose the connection
        yield WaitDBus( self.usage.Suspend )
        
        print "OK"
        yield True

        
if __name__ == '__main__':
    loop = gobject.MainLoop()
    def on_start():
        try:
            yield Test()
        finally:
            loop.quit() # whatever happend, we need to stop the mainloop at the end

    gobject.idle_add(Tasklet(generator=on_start()).start)
    loop.run()
    print "Exit"

