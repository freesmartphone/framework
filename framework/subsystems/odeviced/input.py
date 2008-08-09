#!/usr/bin/env python
"""
Open Device Daemon - A plugin for input device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

MODULE_NAME = "odeviced.input"
__version__ = "0.9.9"

from framework.patterns import asyncworker
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
from config import config

import gobject
import dbus.service
import itertools, sys, os, time, struct

import logging
logger = logging.getLogger( MODULE_NAME )

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
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )

        configvalue = config.getValue( MODULE_NAME, "ignoreinput", "" )
        ignoreinput = [ int(value) for value in configvalue.split(',') if value != "" ]

        self.input = {}
        for i in itertools.count():
            if i in ignoreinput:
                logger.info( "skipping input node %d due to configuration" % ( i ) )
                continue
            try:
                f = os.open( "/dev/input/event%d" % i, os.O_NONBLOCK )
            except OSError, e:
                logger.debug( "can't open /dev/input/event%d: %s. Assuming it doesn't exist.", i, e )
                break
            else:
                self.input[f] = "event%d" % i

        logger.info( "opened %d input file descriptors", len( self.input ) )
        # FIXME what to do if initialization of a module fails?s

        self.watches = {}
        self.events = {}
        self.reportheld = {}

        for option in config.getOptions( MODULE_NAME ):
            if option.startswith( "report" ):
                try:
                    name, typ, code, reportheld = config.getValue( MODULE_NAME, option ).split( ',' )
                    code = int(code)
                    reportheld = bool(int(reportheld))
                except ValueError:
                    logger.warning( "wrong syntax for switch definition '%s': ignoring." % option )
                else:
                    self.watchForEvent( name, typ, code, reportheld )

        if len( self.input ):
            self.launchStateMachine()

    def watchForEvent( self, name, action, inputcode, reportheld ):
        logger.debug( "adding watch for %s %s %s %s", name, action, inputcode, reportheld )
        try:
            action = self.action[action]
        except KeyError:
            logger.error( "don't know how to deal with event action %s", action )
            return False
        else:
            self.watches[ ( action, inputcode ) ] = name
            self.reportheld[ ( action, inputcode ) ] = reportheld

    def launchStateMachine( self ):
        for i in self.input:
            gobject.io_add_watch( i, gobject.IO_IN, self.onInputActivity )

    def onInputActivity( self, source, condition ):
        data = os.read( source, 512 )
        events = [ data[i:i+input_event_size] for i in range( 0, len(data), input_event_size ) ]
        for e in events:
            timestamp, microseconds, typ, code, value = struct.unpack( input_event_struct, e )
            if typ != 0x00: # ignore EV_SYN (synchronization event)
                self.enqueue( timestamp, typ, code, value )
                if __debug__: logger.debug( "read %d bytes from fd %d ('%s'): %s" % ( len( data ), source, self.input[source], (typ, code, value) ) )
        return True

    def onProcessElement( self, event ):
        timestamp, typ, code, value = event
        if ( typ, code ) in self.watches:
            if value == 0x01: # pressed
                if self.reportheld[ typ, code ]:
                    timeout = gobject.timeout_add_seconds( 1, self.callbackKeyHeldTimeout, typ, code )
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
                        gobject.source_remove( timeout )
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
        logger.info( "name %s %s %s" % ( name, action, seconds ) )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """
    Initialize dbus plugin objects.
    """
    return [ Input( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

