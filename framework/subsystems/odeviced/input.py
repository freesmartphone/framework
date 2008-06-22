#!/usr/bin/env python
"""
Open Device Daemon - A plugin for input device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.1.0"

import dbus.service
import sys, os, time, struct
from Queue import Queue
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from gobject import io_add_watch, IO_IN, source_remove, timeout_add, timeout_add_seconds, idle_add
from itertools import count
from helpers import LOG, DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
import ConfigParser

"""
    struct timeval {
        (unsigned long) time_t          tv_sec;         /* seconds */
        (unsigned long) suseconds_t     tv_usec;        /* microseconds */
    };
    (unsigned short) __u16 type;
    (unsigned short) __u16 code;
    (signed int) __s32 value;


"""
input_event_struct = "@LLHHi"
input_event_size = struct.calcsize( input_event_struct )

#----------------------------------------------------------------------------#
class Input( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Input"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Input"

    def __init__( self, bus, config, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Input"
        dbus.service.Object.__init__( self, bus, self.path )
        self.config = config
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        try:
            ignoreinput = self.config.get( "input", "ignoreinput" )
        except ConfigParser.Error:
            ignoreinput = tuple()
        else:
            ignoreinput = [ int(value) for value in ignoreinput.split(',') ]

        self.input = {}
        for i in count():
            if i in ignoreinput:
                LOG( LOG_INFO, __name__, "skipping input node %d due to configuration" % i )
                continue
            try:
                f = os.open( "/dev/input/event%d" % i, os.O_NONBLOCK )
            except OSError, e:
                LOG( LOG_ERR, "can't open /dev/input/event%d: %s" % ( i, e ) )
                break
            else:
                self.input[f] = "event%d" % i

        LOG( LOG_DEBUG, "opened %d input file descriptors" % len( self.input ) )

        self.q = Queue()
        self.watches = {}
        self.events = {}

        # FIXME parse these ones from framework.config after milestone 1
        #self.watchForEvent( "Aux", "key", 0x1e )
        #self.watchForEvent( "Power", "key", 0x19 )
        self.watchForEvent( "AUX", "key", 169 )
        self.watchForEvent( "POWER", "key", 116 )

        if len( self.input ):
            self.launchStateMachine()

    def watchForEvent( self, name, action, inputcode ):
        if not action in ( "key" ):
            LOG( LOG_ERR, "don't know how to deal with event action", action )
            return False
        else:
            action = 0x01 # EV_KEY
        self.watches[ ( action, inputcode ) ] = name

    def launchStateMachine( self ):
        for i in self.input:
            io_add_watch( i, IO_IN, self.onInputActivity )

    def onInputActivity( self, source, condition ):
        data = os.read( source, 512 )
        LOG( LOG_DEBUG, self.__class__.__name__, "read %d bytes from fd %d ('%s')" % ( len( data ), source, self.input[source] ) )
        events = [ data[i:i+input_event_size] for i in range( 0, len(data), input_event_size ) ]
        for e in events:
            timestamp, microseconds, typ, code, value = struct.unpack( input_event_struct, e )
            if typ != 0x00: # ignore EV_SYN (synchronization event)
                self.q.put( ( timestamp, typ, code, value ) )
        idle_add( self.processEvents )
        return True

    def processEvents( self ):
        if self.q.empty():
            return False
        self.processEvent( self.q.get() )
        return not self.q.empty() # call me again, if there's more data in the queue

    def processEvent( self, event ):
        timestamp, typ, code, value = event
        if ( typ, code ) in self.watches:
            if value == 0x01: # pressed
                timeout = timeout_add_seconds( 1, self.callbackKeyHeldTimeout, typ, code )
                self.events[ ( typ, code ) ] = timestamp, timeout
                self.Event( self.watches[ ( typ, code ) ], "pressed", 0 )
            elif value == 0x00: # released
                self.Event( self.watches[ ( typ, code ) ], "released", 0 )
                try:
                    timestamp, timeout = self.events[ ( typ, code ) ]
                except KeyError:
                    LOG( LOG_ERROR, "potential logic problem, key released before pressed. watches are", self.watches, "events are", self.events )
                else:
                    source_remove( timeout )
                    del self.events[ ( typ, code ) ]

    def callbackKeyHeldTimeout( self, typ, code ):
        timestamp, timeout = self.events[ ( typ, code ) ]
        self.Event( self.watches[ ( typ, code ) ], "held", int( time.time() ) - timestamp )
        return True # call me again, after another second
    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "ssi" )
    def Event( self, name, action, seconds ):
        LOG( LOG_INFO, __name__, "event", name, action, seconds )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""

    return [ Input( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    #proxy = bus.get_object( DBUS_INTERFACE_PREFIX, Input.DBUS_INTERFACE )

