#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later

Package: ogsmd.modems.abstract
Module: modem
"""

from ogsmd.gsm.decor import logged
from framework.config import LOG, LOG_ERR, LOG_INFO, LOG_DEBUG

import gobject

#=========================================================================#
class AbstractModem( object ):
#=========================================================================#
    """This class abstracts a GSM Modem."""
    instance = None

    @logged
    def __init__( self, object, bus, *args, **kwargs ):
        """
        Initialize
        """
        assert self.__class__.__name__ != "AbstractModem", "can't instanciate pure virtual class"
        assert AbstractModem.instance is None
        AbstractModem.instance = self

        self._channels = {}                     # container for channel instances
        self._object = object                   # dbus object
        self._bus = bus                         # dbus bus
        self._simPinState = "unknown"           # SIM PIN state
        self._simReady = "unknown"              # SIM data access state

        self._phonebookIndices = None, None      # min. index, max. index

    def open( self, callback ):
        """
        Trigger opening channels from inside mainloop.
        """
        self._counter = len( self._channels )
        if ( self._counter ):
            gobject.idle_add( self._initChannels, callback )

    def channel( self, category ):
        """
        Returns the communication channel for certain command category.
        """
        assert False, "pure virtual method called"

    def channels( self ):
        """
        Returns the names of the communication channels.
        """
        return self._channels.keys()

    def inject( self, channel, string ):
        """
        Injects a string to a channel.
        """
        self._channels[channel].readyToRead( string )

    def simPinState( self ):
        """
        Returns the SIM PIN state
        """
        return self._simPinState

    def simReady( self ):
        """
        Returns the SIM availability state.
        """
        return self._simReady

    def stateAntennaOn( self ):
        """
        Notify channels that the antenna is now powered on.
        """
        for channel in self._channels.itervalues():
            channel.modemStateAntennaOn()

    def setSimPinState( self, state ):
        """
        Set and notify channels about a new SIM PIN state.
        """
        self._simPinState = state
        if state == "READY":
            for channel in self._channels.itervalues():
                channel.modemStateSimUnlocked()

    def setSimReady( self, ready ):
        """
        Set and notify channels about a SIM data accessibility.
        """
        self._simReady = ready
        if ready == True:
            for channel in self._channels.itervalues():
                channel.modemStateSimReady()

    def setPhonebookIndices( self, first, last ):
        self._phonebookIndices = first, last

    def phonebookIndices( self ):
        return self._phonebookIndices

    def prepareForSuspend( self, ok_callback, error_callback ):
        """
        Prepares the modem for suspend.
        """
        # FIXME can we refactor this into a generic useful callback/object adapter class?
        class MyOk(object):
            def __init__( self, *args, **kwargs ):
                assert args == (), "only keyword arguments allowed"
                for key, value in kwargs.iteritems():
                    if key.startswith( "CL_" ):
                        setattr( self.__class__, key[3:], value )
                    else:
                        setattr( self, key, value )

            def __call__( self, channel ):
                LOG( LOG_DEBUG, "prepareForSuspend ACK from channel", channel, "received" )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.ok()

        class MyError(MyOk):
            def __call__( self, channel ):
                LOG( LOG_DEBUG, "prepareForSuspend NACK from channel", channel, "received" )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.error()

        ok = MyOk( CL_counter = len( self._channels ), ok = ok_callback )
        error = MyError( error = error_callback )
        for channel in self._channels.values():
            channel.suspend( ok, error )

    def recoverFromSuspend( self, ok_callback, error_callback ):
        """
        Recovers the modem from suspend.
        """
        # FIXME can we refactor this into a generic useful callback/object adapter class?
        class MyOk(object):
            def __init__( self, *args, **kwargs ):
                assert args == (), "only keyword arguments allowed"
                for key, value in kwargs.iteritems():
                    if key.startswith( "CL_" ):
                        setattr( self.__class__, key[3:], value )
                    else:
                        setattr( self, key, value )

            def __call__( self, channel ):
                LOG( LOG_DEBUG, "prepareForSuspend ACK from channel", channel, "received" )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.ok()

        class MyError(MyOk):
            def __call__( self, channel ):
                LOG( LOG_DEBUG, "prepareForSuspend NACK from channel", channel, "received" )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.error()

        ok = MyOk( CL_counter = len( self._channels ), ok = ok_callback )
        error = MyError( error = error_callback )
        for channel in self._channels.values():
            channel.resume( ok, error )

    #
    # internal API
    #
    def _initChannels( self, callback ):
        for channel in self._channels:
            if not self._channels[channel].isOpen():
                LOG( LOG_DEBUG, "trying to open", channel )
                if not self._channels[channel].open():
                    LOG( LOG_ERR, "could not open channel", channel, "retrying in 2 seconds" )
                    gobject.timeout_add_seconds( 2, self._initChannels, callback )
                else:
                    self._counter -= 1
                    if not self._counter:
                        gobject.idle_add( callback )
        return False # don't call me again

    @classmethod
    def communicationChannel( cls, category ):
        return cls.instance.channel( category )

#=========================================================================#
