#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later

Package: ogsmd.modems.abstract
Module: modem
"""

# FIXME: The modem should really be a sigleton

__version__ = "0.9.9.3"
MODULE_NAME = "ogsmd.modem.abstract"

import gobject
import sys, types

import logging
logger = logging.getLogger( MODULE_NAME )

FALLBACK_TIMEOUT = 30

#=========================================================================#
class AbstractModem( object ):
#=========================================================================#
    """This class abstracts a GSM Modem."""
    instance = None

    def __init__( self, dbus_object, bus, *args, **kwargs ):
        """
        Initialize
        """
        assert self.__class__.__name__ != "AbstractModem", "can't instanciate pure virtual class"
        # FIXME make sure only one modem exists
        AbstractModem.instance = self

        self._channels = {}                     # container for channel instances
        self._object = dbus_object              # dbus object
        self._bus = bus                         # dbus bus
        self._simPinState = "unknown"           # SIM PIN state
        self._simReady = "unknown"              # SIM data access state
        self._data = {}                         # misc modem-wide data, set/get from channels
        self._phonebookIndices = {}             # min. index, max. index

        self._data["sim-buffers-sms"] = True
        self._data["sms-buffered-cb"] = "2,1,2,1,1"
        self._data["sms-buffered-nocb"] = "2,1,0,0,0"
        # FIXME: Might be bad as default, since not all modems necessarily support that
        self._data["sms-direct-cb"] = "2,2,2,1,1" # what about a,3,c,d,e?
        self._data["sms-direct-nocb"] = "2,2,0,0,0" # dito

        self._data["pppd-configuration"] = [ \
            '115200',
            'nodetach',
            'crtscts',
            'defaultroute',
            'debug',
            'hide-password',
            'holdoff', '3',
            'ipcp-accept-local',
            'ktune',
            #'lcp-echo-failure', '10',
            #'lcp-echo-interval', '20',
            'ipcp-max-configure', '4',
            'lock',
            'noauth',
            #'demand',
            'noipdefault',
            'novj',
            'novjccomp',
            #'persist',
            'proxyarp',
            'replacedefaultroute',
            'usepeerdns',
        ]

        self._charsets = { \
            "DEFAULT":      "gsm_default",
            "PHONEBOOK":    "gsm_ucs2",
            "USSD":         "gsm_ucs2",
            }

        self._data["cancel-outgoing-call"] = "H" # default will kill all connections

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

    def reinit( self ):
        """
        Closes and reopens the communication channels, also triggering
        resending the initialization commands on every channel.
        """
        self.close()
        for channel in self._channels.values():
            channel._sendCommands( "init" ) # just enqueues them for later
        # FIXME no error handling yet
        self.open( lambda: None, lambda foo: None )

    def data( self, key, defaultValue=None ):
        return self._data.get( key, defaultValue )

    def setData( self, key, value ):
        self._data[key] = value

    def numberToPhonebookTuple( self, nstring ):
        """
        Returns a phonebook tuple.
        """
        if type( nstring ) != types.StringType():
            # even though we set +CSCS="UCS2" (modem charset), the name is always encoded in text format, not PDU.
            nstring = nstring.encode( "iso-8859-1" )

        if nstring[0] == '+':
            return nstring[1:], 145
        else:
            return nstring, 129

    def channel( self, category ):
        """
        Returns the communication channel for certain command category.
        """
        sys.exit( -1 ) # pure virtual method called

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

    def setPhonebookIndices( self, category, first, last ):
        """
        Set phonebook valid indices interval for a given phonebook
        """
        self._phonebookIndices[category] = first, last

    def phonebookIndices( self, category ):
        try:
            first, last = self._phonebookIndices[category]
        except KeyError:
            return None, None
        else:
            return first, last

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
        if iteration == 7:
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
