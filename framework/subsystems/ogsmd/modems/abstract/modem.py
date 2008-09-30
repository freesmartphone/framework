#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later

Package: ogsmd.modems.abstract
Module: modem
"""

# FIXME: The modem should really be a sigleton

from ogsmd.gsm.decor import logged

import gobject

import logging
logger = logging.getLogger( "ogsmd.modem.abstract" )

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
        # FIXME make sure only one modem exists
        AbstractModem.instance = self

        self._channels = {}                     # container for channel instances
        self._object = object                   # dbus object
        self._bus = bus                         # dbus bus
        self._simPinState = "unknown"           # SIM PIN state
        self._simReady = "unknown"              # SIM data access state
        self._data = {}                         # misc modem-wide data, set/get from channels

        self._phonebookIndices = None, None      # min. index, max. index

    def open( self, on_ok, on_error ):
        """
        Triggers opening the channels on this modem.

        The actual opening will happen from inside mainloop.
        """
        self._counter = len( self._channels )
        if ( self._counter ):
            gobject.idle_add( self._initChannels, on_ok, on_error )

    def close( self ): # SYNC
        """
        Closes the communication channels.
        """
        # FIXME: A really good way would be to stop accepting new commands,
        # giving it time to drain the queues, and then closing all channels.
        for channel in self._channels.values():
            # FIXME: We're throwing away the result here :/
            channel.close()

    def data( self, key, defaultValue=None ):
        return self._data.get( key, defaultValue )

    def setData( self, key, value ):
        self._data[key] = value

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
                logger.debug( "prepareForSuspend ACK from channel %s received" % channel )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.ok()

        class MyError(MyOk):
            def __call__( self, channel ):
                logger.debug( "prepareForSuspend NACK from channel %s received" % channel )
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
                logger.debug( "recoverFromSuspend ACK from channel %s received" % channel )
                self.__class__.counter -= 1
                if self.__class__.counter == 0:
                    self.ok()

        class MyError(MyOk):
            def __call__( self, channel ):
                logger.debug( "recoverFromSuspend NACK from channel %s received" % channel )
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
    def _initChannels( self, on_ok, on_error, iteration=1 ):
        if iteration == 5:
            # we did try to open the modem 5 times -- giving up now
            on_error()
        # try to open all channels
        for channel in self._channels:
            if not self._channels[channel].isOpen():
                logger.debug( "trying to open channel %s" % channel )
                if not self._channels[channel].open():
                    logger.error( "could not open channel %s, retrying in 2 seconds" % channel )
                    gobject.timeout_add_seconds( 2, self._initChannels, on_ok, on_error, iteration+1 )
                else:
                    self._counter -= 1
                    if not self._counter:
                        on_ok()
        return False # don't call me again

    @classmethod
    def communicationChannel( cls, category ):
        return cls.instance.channel( category )

#=========================================================================#
