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
__version__ = "0.9.10.4"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile
from framework.config import config
from framework import resource

import gobject
import dbus.service
import itertools, os, sys
import errno

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

        self.defaultTimeouts = dict( awake=-1, busy=-1, idle=10, idle_dim=20, idle_prelock=12, lock=2, suspend=20 )
        self.timeouts = self.defaultTimeouts.copy()
        self.states = "awake busy idle idle_dim idle_prelock lock suspend".split()
        self.validStates = set(self.states)
        self.allowedStates = set(self.states)
        self.state = self.states[0]

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

        # override default timeouts with configuration (if set)
        for key in self.timeouts:
            timeout = config.getInt( MODULE_NAME, key, self.defaultTimeouts[key] )
            self.timeouts[key] = timeout
            if timeout == 0:
                self.allowedStates.remove( key )
            logger.debug( "(re)setting %s timeout to %d" % ( key, self.timeouts[key] ) )

        self.next = None
        self.timeout = 0

        self.setState( "busy" )

        if len( self.input ):
            self.timer = gobject.timeout_add_seconds( 1, self.onTimer )

    def prohibitStateTransitionTo( self, state ):
        # FIXME do some reference counting?
        self.allowedStates.remove( state )
        logger.info( "allowed idle states now: %s " % self.allowedStates )
        self.setState( self.state )

    def allowStateTransitionTo( self, state ):
        self.allowedStates.add( state )
        logger.info( "allowed idle states now: %s " % self.allowedStates )
        self.setState( self.state )

    def onTimer( self ):
        active = False
        for i in self.input:
            active |= self.checkActivity( i )
        logger.debug( "active = %s", active )
        if active:
            self.setState( "busy" )
        else:
            self.idletime += 1
            self.checkTimeout()
        return True

    def checkActivity( self, source ):
        active = False
        try:
            data = True
            while data:
                data = os.read( source, 4096 )
                if data:
                    active = True
                #logger.debug( "read %d bytes from fd %d ('%s')" % ( len( data ), source, self.input[source] ) )
            return active
        except OSError, e:
            if e[0] == errno.EAGAIN:
                return active
            logger.exception( "error while reading:" )
            return False

    def checkTimeout( self ):
        if self.idletime >= self.timeout:
            self.setState( self.next )

    def setState( self, state ):
        newIndex = 0
        for x in self.states[1:self.states.index( state )+1]:
            if not x in self.allowedStates:
                break
            newIndex += 1
        newState = self.states[newIndex]
        if not self.state == newState:
            self.State( newState )
            self.state = newState
        nextIndex = min( newIndex + 1, len( self.states) - 1 )
        while nextIndex and not self.states[nextIndex] in self.allowedStates:
            nextIndex -= 1
        self.idletime = 0
        self.next = self.states[nextIndex]
        self.timeout = self.timeouts[ self.next ]

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
        self.timeouts[state] = timeout
        # FIXME refcounts instead?
        if timeout:
            self.allowedStates.add( state )
        else:
            self.allowedStates.discard( state )
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
            self.setState( state )

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
        on_ok()

    def _disable( self, on_ok, on_error ):
        """
        Disable (inherited from Resource)
        """
        IdleNotifier.instance().allowStateTransitionTo( "idle_dim" )
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
