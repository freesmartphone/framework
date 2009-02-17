#!/usr/bin/env python
"""
Open Device Daemon - A plugin for generic idle state notification

The IdleNotifier signalizes while the system goes through different idle states.
Another plugin or an application can use the state notifications to act accordingly.
Known states and possible use cases:

- "awake": after suspend and on startup, power up peripherals and prepare I/O
- "busy": receiving input from input events
- "idle": not receiving any input
- "idle_dim": not receiving input for "a while", dim the display and/or clock down the CPU
- "idle_prelock": not receiving input for "a long while", prepare to put some more I/O to sleep
- "lock": not receiving input for "very long", lock the display now
- "suspend": shut down CPU, suspend to RAM or DISK

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later
"""

MODULE_NAME = "odeviced.idlenotifier"
__version__ = "0.9.10.3"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile
from framework.config import config
from framework import resource

import gobject
import dbus.service
import itertools, os, sys

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class InvalidState( dbus.DBusException ):
#=========================================================================#
    _dbus_error_name = "org.freesmartphone.IdleNotifier.InvalidState"

#=========================================================================#
class IdleNotifier( dbus.service.Object ):
#=========================================================================#
    """A Dbus Object implementing org.freesmartphone.Device.IdleNotifier"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".IdleNotifier"

    _instance = None

    @classmethod
    def instance( klass ):
        return klass._instance

    def __init__( self, bus, index, extranodes ):
        self.__class__._instance = self
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/IdleNotifier/%s" % index
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s", self.__class__.__name__, __version__, self.interface, self.path )

        self.state = "awake"
        self.timeouts = { \
                        "none": -1, # dummy state
                        "idle": 10,
                        "idle_dim": 20,
                        "idle_prelock": 12,
                        "lock": 2,
                        "suspend": 20, \
                        }
        self.states = "awake none busy idle idle_dim idle_prelock lock suspend".split()

        configvalue = config.getValue( MODULE_NAME, "ignoreinput", "" )
        ignoreinput = [ int(value) for value in configvalue.split(',') if value != "" ]

        self.input = {}
        for i in itertools.count():
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

        self.readTimeoutsFromConfig()

        # states without timeout
        self.timeouts["busy"] = -1
        self.validStates = self.timeouts.keys()
        self.timeouts["awake"] = -1

        self.timeout = None

        if len( self.input ):
            self.launchStateMachine()

    def readTimeoutsFromConfig( self ):
        # override default timeouts with configuration (if set)
        for key in self.timeouts:
            self.timeouts[key] = config.getInt( MODULE_NAME, key, self.timeouts[key] )
            logger.debug( "setting %s timeout to %d" % ( key, self.timeouts[key] ) )

    def prohibitStateTransitionTo( self, state ):
        # stop falling into in the future
        self.timeouts[state] = 0
        # check whether said state would be the next state
        if state == self.nextState( self.state ):
            # kill timeout
            if self.timeout is not None:
                gobject.source_remove( self.timeout )
        # then, check whether we _are_ in that state
        if state == self.state:
            # kill timeout
            if self.timeout is not None:
                gobject.source_remove( self.timeout )
            # and go into the previous state
            self.onState( self.previousState( self.state ) )

    def allowStateTransitionTo( self, state ):
        self.readTimeoutsFromConfig()
        # stop timer
        if self.timeout is not None:
            gobject.source_remove( self.timeout )
        # relaunch timer
        self.onState( self.state )

    def launchStateMachine( self ):
        for i in self.input:
            gobject.io_add_watch( i, gobject.IO_IN, self.onInputActivity )
        self.timeout = gobject.timeout_add_seconds( 2, self.onState, "idle" )

    def previousState( self, state ):
        index = self.states.index( state )
        nextIndex = ( index - 1 ) % len(self.states)
        return self.states[nextIndex]

    def nextState( self, state ):
        index = self.states.index( state )
        nextIndex = ( index + 1 ) % len(self.states)
        return self.states[nextIndex]

    def onInputActivity( self, source, condition ):
        data = os.read( source, 512 )
        if __debug__: logger.debug( "read %d bytes from fd %d ('%s')" % ( len( data ), source, self.input[source] ) )
        if self.state != "busy":
            if self.timeout is not None:
                gobject.source_remove( self.timeout )
            self.onState( "busy" )
        return True

    def onState( self, state ):
        self.State( state )
        nextState = self.nextState( state )
        timeout = self.timeouts[ nextState ]
        if timeout > 0:
            self.timeout = gobject.timeout_add_seconds( timeout, self.onState, nextState )
        else:
            logger.debug( "Timeout for %s disabled, not falling into this state next." % nextState )

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
    def GetState( self ):
        return self.state

    @dbus.service.method( DBUS_INTERFACE, "", "a{si}" )
    def GetTimeouts( self ):
        return self.timeouts

    @dbus.service.method( DBUS_INTERFACE, "si", "" )
    def SetTimeout( self, state, timeout ):
        if not state in self.validStates:
            raise InvalidState( "valid states are: %s" % self.validStates )
        elif timeout is not None:
            self.timeouts[state] = timeout
            config.setValue(MODULE_NAME, state, timeout)
            config.sync()

    @dbus.service.method( DBUS_INTERFACE, "s", "" )
    def SetState( self, state ):
        if state == self.state:
            logger.debug( "state already active. ignoring request" )
            return
        if not state in self.validStates:
            raise InvalidState( "valid states are: %s" % self.validStates )
        else:
            if self.timeout is not None:
                gobject.source_remove( self.timeout )
            self.onState( state )

#=========================================================================#
class CpuResource( resource.Resource ):
#=========================================================================#
    def __init__( self, bus ):
        """
        Init.
        """
        self.path = "/org/freesmartphone/Device/CPU"
        dbus.service.Object.__init__( self, bus, self.path )
        resource.Resource.__init__( self, bus, "CPU" )
        logger.info( "%s %s initialized." % ( self.__class__.__name__, __version__ ) )

    #
    # dbus org.freesmartphone.Resource [inherited from framework.Resource]
    #
    def _enable( self, on_ok, on_error ):
        """
        Enable (inherited from Resource)
        """
        IdleNotifier.instance().prohibitStateTransitionTo( "suspend" )
        on_ok()

    def _disable( self, on_ok, on_error ):
        """
        Disable (inherited from Resource)
        """
        IdleNotifier.instance().allowStateTransitionTo( "suspend" )
        on_ok()

    def _suspend( self, on_ok, on_error ):
        """
        Suspend (inherited from Resource)
        """
        # should actually trigger an error, since suspending CPU is not allowed
        on_ok()

    def _resume( self, on_ok, on_error ):
        """
        Resume (inherited from Resource)
        """
        # should actually trigger an error, since suspending CPU is not allowed
        on_ok()

#=========================================================================#
class DisplayResource( resource.Resource ):
#=========================================================================#
    def __init__( self, bus ):
        """
        Init.
        """
        self.path = "/org/freesmartphone/Device/Display"
        dbus.service.Object.__init__( self, bus, self.path )
        resource.Resource.__init__( self, bus, "Display" )
        logger.info( "%s %s initialized." % ( self.__class__.__name__, __version__ ) )

    #
    # dbus org.freesmartphone.Resource [inherited from framework.Resource]
    #
    def _enable( self, on_ok, on_error ):
        """
        Enable (inherited from Resource)
        """
        IdleNotifier.instance().prohibitStateTransitionTo( "idle_dim" )
        IdleNotifier.instance().SetState( "busy" )
        # FIXME should we do something else here?
        on_ok()

    def _disable( self, on_ok, on_error ):
        """
        Disable (inherited from Resource)
        """
        IdleNotifier.instance().allowStateTransitionTo( "idle_dim" )
        # FIXME should we do something else here?
        on_ok()

    def _suspend( self, on_ok, on_error ):
        """
        Suspend (inherited from Resource)
        """
        # FIXME should we do something here?
        on_ok()

    def _resume( self, on_ok, on_error ):
        """
        Resume (inherited from Resource)
        """
        # FIXME should we do something here?
        on_ok()

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ IdleNotifier( controller.bus, 0, [] ),
             CpuResource( controller.bus ),
             DisplayResource( controller.bus ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
