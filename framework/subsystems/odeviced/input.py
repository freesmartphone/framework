#!/usr/bin/env python
"""
Open Device Daemon - A plugin for input device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.0"

from patterns import asyncworker
import dbus.service
from gobject import io_add_watch, IO_IN, source_remove, timeout_add, timeout_add_seconds, idle_add
from itertools import count
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
import ConfigParser
import sys, os, time, struct

import logging
logger = logging.getLogger('odeviced')

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
class Input( dbus.service.Object, asyncworker.AsyncWorker ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Input"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Input"

    action = { "key": 1, "switch": 5 }

    def __init__( self, bus, config, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Input"
        dbus.service.Object.__init__( self, bus, self.path )
        asyncworker.AsyncWorker.__init__( self )
        self.config = config
        logger.info( "input: %s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        try:
            ignoreinput = self.config.get( "input", "ignoreinput" )
        except ConfigParser.Error:
            ignoreinput = tuple()
        else:
            ignoreinput = [ int(value) for value in ignoreinput.split(',') ]

        self.input = {}
        for i in count():
            if i in ignoreinput:
                logger.info( "input: skipping input node %d due to configuration" % ( i ) )
                continue
            try:
                f = os.open( "/dev/input/event%d" % i, os.O_NONBLOCK )
            except OSError, e:
                logger.debug( "input: can't open /dev/input/event%d: %s. Assuming it doesn't exist.", i, e )
                break
            else:
                self.input[f] = "event%d" % i

        logger.info( "input: opened %d input file descriptors", len( self.input ) )

        self.watches = {}
        self.events = {}
        self.reportheld = {}

        for option in config.getOptions( "input" ):
            if option.startswith( "report" ):
                try:
                    name, typ, code, reportheld = config.get( "input", option ).split( ',' )
                except ValueError:
                    pass
                else:
                    self.watchForEvent( name, typ, int(code), bool( int( reportheld ) ) )

        if len( self.input ):
            self.launchStateMachine()

    def watchForEvent( self, name, action, inputcode, reportheld ):
        logger.debug( "input: adding watch for %s %s %s %s", name, action, inputcode, reportheld )
        try:
            action = self.action[action]
        except KeyError:
            logger.error( "input: don't know how to deal with event action %s", action )
            return False
        else:
            self.watches[ ( action, inputcode ) ] = name
            self.reportheld[ ( action, inputcode ) ] = reportheld

    def launchStateMachine( self ):
        for i in self.input:
            io_add_watch( i, IO_IN, self.onInputActivity )

    def onInputActivity( self, source, condition ):
        data = os.read( source, 512 )
        events = [ data[i:i+input_event_size] for i in range( 0, len(data), input_event_size ) ]
        for e in events:
            timestamp, microseconds, typ, code, value = struct.unpack( input_event_struct, e )
            if typ != 0x00: # ignore EV_SYN (synchronization event)
                self.enqueue( timestamp, typ, code, value )
                if __debug__: logger.debug( "input: read %d bytes from fd %d ('%s'): %s" % ( len( data ), source, self.input[source], (typ, code, value) ) )
        return True

    def onProcessElement( self, event ):
        timestamp, typ, code, value = event
        if ( typ, code ) in self.watches:
            if value == 0x01: # pressed
                if self.reportheld[ typ, code ]:
                    timeout = timeout_add_seconds( 1, self.callbackKeyHeldTimeout, typ, code )
                else:
                    timeout = 0
                self.events[ ( typ, code ) ] = timestamp, timeout
                self.Event( self.watches[ ( typ, code ) ], "pressed", 0 )
            elif value == 0x00: # released
                self.Event( self.watches[ ( typ, code ) ], "released", 0 )
                try:
                    timestamp, timeout = self.events[ ( typ, code ) ]
                except KeyError:
                    logger.warning( "potential logic problem, key released before pressed. watches are %s events are %s" % ( self.watches, self.events ) )
                else:
                    if timeout:
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
        logger.info( "input: name %s %s %s" % ( name, action, seconds ) )

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
