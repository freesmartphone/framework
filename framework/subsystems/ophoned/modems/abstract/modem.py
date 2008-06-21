#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: abstract
Module: modem
"""

from ophoned.gsm.decor import logged
from config import LOG, LOG_ERR, LOG_INFO, LOG_DEBUG

import gobject

#=========================================================================#
class AbstractModem( object ):
#=========================================================================#
    instance = None

    @logged
    def __init__( self, object, bus, *args, **kwargs ):
        """
        Initialize
        """
        assert self.__class__.__name__ != "AbstractModem", "can't instanciate pure virtual class"
        assert AbstractModem.instance is None
        AbstractModem.instance = self

        # container for channel instances
        self._channels = {}
        self._object = object
        self._bus = bus
        self._sCounter = None

    def open( self, callback ):
        """
        Trigger opening channels from inside mainloop
        """
        self._counter = len( self._channels )
        if ( self._counter ):
            gobject.idle_add( self._initChannels, callback )

    def channel( self, category ):
        assert False, "pure virtual method called"

    def prepareForSuspend( self, ok_callback, error_callback ):
        """
        Prepare modem for suspend
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
        Recover modem from suspend
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
