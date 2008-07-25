#!/usr/bin/env python
"""
Open Device Daemon - A plugin for generic idle state notification

The IdleNotifier signalizes while the system goes through different idle states.
Another plugin or an application can use the state notifications to act accordingly.
Known states and possible use cases:

- AWAKE: after suspend and on startup, power up peripherals and prepare I/O
- BUSY: receiving input from input events
- IDLE: not receiving any input
- IDLE_DIM: not receiving input for "a while", dim the display and/or clock down the CPU
- IDLE_PRELOCK: not receiving input for "a long while", prepare to put some more I/O to sleep
- LOCK: not receiving input for "very long", lock the display now
- SUSPEND: shut down CPU, suspend to RAM or DISK

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.1"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile

import gobject
import dbus.service
from itertools import count
import ConfigParser
import os, sys

import logging
logger = logging.getLogger( "odeviced.idlenotifier" )

#----------------------------------------------------------------------------#
class IdleNotifier( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.IdleNotifier"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".IdleNotifier"

    def __init__( self, bus, config, index, extranodes ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/IdleNotifier/%s" % index
        dbus.service.Object.__init__( self, bus, self.path )
        self.config = config
        logger.info( "%s initialized. Serving %s at %s", self.__class__.__name__, self.interface, self.path )

        self.state = "AWAKE"

        if "ODEVICED_DEBUG" in os.environ:
            self.timeouts = { \
                            "IDLE": 2,
                            "IDLE_DIM": 2,
                            "IDLE_PRELOCK": 2,
                            "LOCK": 2,
                            "SUSPEND": 10,
                            "AWAKE": -1, \
                            }
        else:
            self.timeouts = { \
                            "IDLE": 10,
                            "IDLE_DIM": 20,
                            "IDLE_PRELOCK": 12,
                            "LOCK": 2,
                            "SUSPEND": 20, \
                            }
        self.validStates = self.timeouts.keys()

        try:
            ignoreinput = self.config.get( "idlenotifier", "ignoreinput" )
        except ConfigParser.Error:
            ignoreinput = tuple()
        else:
            ignoreinput = [ int(value) for value in ignoreinput.split(',') ]

        self.input = {}
        for i in count():
            if i in ignoreinput:
                logger.info( "skipping input node %d due to configuration" % i )
                continue
            try:
                f = os.open( "/dev/input/event%d" % i, os.O_NONBLOCK )
            except OSError, e:
                logger.debug( "can't open /dev/input/event%d: %s. Assuming it doesn't exist." % ( i, e ) )
                break
            else:
                self.input[f] = "event%d" % i

        logger.info( "opened %d input file descriptors" % len( self.input ) )

        for key in self.timeouts:
            try:
                self.timeouts[key] = self.config.getint( "idlenotifier", key.lower() )
            except ConfigParser.Error:
                logger.info( "timeout for %s not configured. using default" % key )

        # states without timeout
        self.timeouts["AWAKE"] = -1
        self.timeouts["BUSY"] = -1

        if len( self.input ):
            self.launchStateMachine()

    def launchStateMachine( self ):
        for i in self.input:
            gobject.io_add_watch( i, gobject.IO_IN, self.onInputActivity )
        self.timeout = gobject.timeout_add_seconds( 2, self.onIdleTimeout )

    def onInputActivity( self, source, condition ):
        data = os.read( source, 512 )
        if __debug__: logger.debug( "read %d bytes from fd %d ('%s')" % ( len( data ), source, self.input[source] ) )
        if self.state == "BUSY":
            pass
        else:
            self.State( "BUSY" )
        gobject.source_remove( self.timeout )
        self.timeout = gobject.timeout_add_seconds( self.timeouts["IDLE"], self.onIdleTimeout )
        return True

    def onIdleTimeout( self ):
        self.State( "IDLE" )
        self.timeout = gobject.timeout_add_seconds( self.timeouts["IDLE_DIM"], self.onIdleDimTimeout )
        return False

    def onIdleDimTimeout( self ):
        self.State( "IDLE_DIM" )
        self.timeout = gobject.timeout_add_seconds( self.timeouts["IDLE_PRELOCK"], self.onIdlePrelockTimeout )
        return False

    def onIdlePrelockTimeout( self ):
        self.State( "IDLE_PRELOCK" )
        self.timeout = gobject.timeout_add_seconds( self.timeouts["LOCK"], self.onLockTimeout )
        return False

    def onLockTimeout( self ):
        self.State( "LOCK" )
        self.timeout = gobject.timeout_add_seconds( self.timeouts["SUSPEND"], self.onSuspendTimeout )
        return False

    def onSuspendTimeout( self ):
        self.State( "SUSPEND" )
        return False

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "s" )
    def State( self, state ):
        logger.info("%s state change to %s", __name__, state)
        self.state = state
    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return "IdleNotifier"

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetState( self ):
        return self.state

    # FIXME: Do we want to allow that at all?
    @dbus.service.method( DBUS_INTERFACE, "s", "" )
    def SetState( self, state ):
        if not state in self.validStates:
            # FIXME: This is wrong
            raise "DBUS_INTERFACE"+".Error.InvalidState"
        elif state == "BUSY":
            gobject.source_remove( self.timeout )
            self.timeout = gobject.timeout_add_seconds( self.timeouts["IDLE"], self.onIdleTimeout )
        # FIXME: handle other states correctly
        self.State( state )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ IdleNotifier( controller.bus, controller.config, 0, [] ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
