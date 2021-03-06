#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2007-2008 M. Dietrich.
(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: channel

This module provides communication channel abstractions that
transport their data over a (virtual) serial line.
"""

__version__ = "0.9.18.2"
MODULE_NAME = "ogsmd.channel"

import parser

import gobject # pygobject

import serial # pyserial
import Queue, fcntl, os, time, types, re # stdlib

import logging
logger = logging.getLogger( MODULE_NAME )

PRIORITY_RTR = -20
PRIORITY_RTS = -10
PRIORITY_HUP = -5

DEFAULT_CHANNEL_TIMEOUT = 5*60

AUTOPREFIX = re.compile( "A?T?(?P<prefix>[\+%!*$\^_&@][A-Z]+)" )

# keys are commands, values are autocomputed response lists
AUTOPREFIX_CACHE = {}

#=========================================================================#
class PeekholeQueue( Queue.Queue ):
#=========================================================================#
    """
    This class extends the Queue with a method to peek at the
    first element without having to remove this from the queue.
    """
    def peek( self ):
        if self.empty():
            return None
        else:
            return self.queue[0]

#=========================================================================#
class VirtualChannel( object ):
#=========================================================================#
    """
    This class represents a sequential serial transport channel.
    """

    #
    # public API
    #
    def __init__( self, pathfactory, name=None, **kwargs ):
        """Construct"""
        self.pathfactory = pathfactory
        self.name = name or self.__class__.__name__
        self.connected = False
        self.watchReadyToSend = None
        self.watchReadyToRead = None
        self.serial = None

    def __repr__( self ):
        return "<%s via %s>" % ( self.__class__.__name__, self.serial.port if self.serial is not None else "unknown" )

    def open( self, path=None ):
        """
        Allocate a channel and opens a serial port.
        Returns True, if successful. False, otherwise.
        """
        if self.connected:
            raise ValueError( "already connected" )

        # gather path
        path = self.pathfactory( self.name )
        if path is None or path == "":
            return False

        # set up serial port object and open it
        logger.info( "%s: initializing" % self )
        self.serial = serial.Serial()
        self.serial.port = str( path )
        self.serial.baudrate = 115200
        self.serial.rtscts = True
        self.serial.xonxoff = False
        self.serial.bytesize = serial.EIGHTBITS
        self.serial.parity = serial.PARITY_NONE
        self.serial.stopbits = serial.STOPBITS_ONE
        self.serial.timeout = None
        try:
            self.serial.open()
        except serial.serialutil.SerialException:
          # Fail gracefully if the device isn't there (yet)
          return False
        if not self.serial.isOpen():
            return False

        # nonblocking
        # fcntl.fcntl( self.serial.fd, fcntl.F_SETFL, os.O_NONBLOCK )

        if not self._hookLowLevelInit():
            return False

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead, priority=PRIORITY_RTR )
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend, priority=PRIORITY_RTS )
        self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self._hup, priority=PRIORITY_HUP )
        self.connected = self.serial.isOpen()
        return self.connected

    def isOpen( self ):
        return self.connected

    def readyToRead( self, data ):
        """
        Called when a data block has been successfully received from the source.

        The default implementation does nothing.
        """
        pass

    def readyToSend( self ):
        """
        Called when the source is ready to receive data.

        The default implementation does nothing.
        """
        pass

    def suspend( self, ok_callback, error_callback ):
        """
        Called when the channel needs to be prepared for a suspend.

        The default implementation does nothing but call the ok_callback
        """
        ok_callback( self )

    def resume( self, ok_callback, error_callback ):
        """
        Called when the channel needs to reinit after resume.

        The default implementation does nothing but call the ok_callback
        """
        ok_callback( self )

    def write( self, data ):
        """Write data to the transport."""
        self._write( data )

    def freeze( self ):
        """Pause reading from the transport."""
        if not self.watchReadyToRead:
            logger.warning( "%s: freeze() called without watch being setup", self )
        else:
            gobject.source_remove( self.watchReadyToRead )

    def thaw( self ):
        """Resume reading from the transport."""
        if not self.watchReadyToRead:
            logger.warning( "%s: thaw() called with watch being already setup", self )
        else:
            self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead, priority=PRIORITY_RTR )

    def close( self ):
        """
        Close the serial port and free the virtual channel.
        Returns True, if serial port could be closed. False, otherwise.
        """
        if not self.connected:
            return True
        if self.watchReadyToSend:
            gobject.source_remove( self.watchReadyToSend )
        if self.watchReadyToRead:
            gobject.source_remove( self.watchReadyToRead )
        if self.watchHUP:
            gobject.source_remove( self.watchHUP )
        if self.serial.isOpen():
            self.serial.close()
        self.connected = self.serial.isOpen()
        return not self.connected

    def port( self ):
        """
        Return name of transport.
        """
        return self.serial.port

    #
    # hooks
    #
    def _hookLowLevelInit( self ):
        """Override, if your channel needs a special low level init."""
        return True

    def _hookPreReading( self ):
        """Override, if the channel needs to be prepared for reading."""
        pass

    def _hookPostReading( self ):
        """Override, if special handling is necessary after reading."""
        pass

    def _hookPreSending( self ):
        """Override, if special handling is necessary before reading."""
        pass

    def _hookPostSending( self ):
        """Override, if special handling is necessary after reading."""
        pass

    def _hookHandleHupCondition( self ):
        """Override, if special handling is necessary on HUP."""
        pass

    #
    # private API
    #
    def _hup( self, source, condition ):
        """Called, if there is a HUP condition on the source."""
        if ( source != self.serial.fd or condition != gobject.IO_HUP ):
            logger.warning( "ready to read, but bogus condition %d or source %d. Ignoring", condition, source )
            return False
        logger.info( "%s: HUP on socket" % self )

        self._hookHandleHupCondition()

        return True # gobject, call me again

    def _readyToRead( self, source, condition ):
        """Called, if data is available on the source."""
        if ( source != self.serial.fd or condition != gobject.IO_IN ):
            logger.warning( "ready to read, but bogus condition %d or source %d. Ignoring", condition, source )
            return False
        #logger.debug( "%s: _readyToRead: watch timeout = %s", self, repr( self.watchTimeout ) )

        self._hookPreReading()
        data = self._lowlevelRead()
        logger.debug( "%s: got %d bytes: %s" % ( self, len(data), repr(data) ) )
        self.readyToRead( data )

        self._hookPostReading()
        return True # gobject, call me again

    def _lowlevelRead( self ):
        """Called to read data from the port."""
        try:
            inWaiting = self.serial.inWaiting()
        except IOError:
            inWaiting = 0
            # should we really continue here?
        return self.serial.read( inWaiting )

    def _lowlevelWrite( self, data ):
        """Called to write data to the port."""
        self.serial.write( data )

    def _readyToSend( self, source, condition ):
        """Called, if source is ready to receive data."""
        if ( source != self.serial.fd or condition != gobject.IO_OUT ):
            logger.warning( "ready to send, but bogus condition %d or source %d. Ignoring", condition, source )
            return False
        #logger.debug( "%s: _readyToSend: watch timeout = %s", self, repr( self.watchTimeout ) )

        if False:
            # make sure nothing has been queued up in the buffer in the meantime
            while self.serial.inWaiting():
                logger.warning( "_readyToSend, but new data already in the buffer. processing" )
                self._readyToRead( self.serial.fd, gobject.IO_IN )

        self._hookPreSending()
        self.readyToSend()
        self.watchReadyToSend = None
        self._hookPostSending()

        return False # gobject, don't call me again

    def __del__( self ):
        """Destruct"""
        self.close()

#=========================================================================#
class QueuedVirtualChannel( VirtualChannel ):
#=========================================================================#
    """
    A virtual channel featuring a command queue.

    Once you put a command into the command queue, it sets up a
    watch on 'ready-to-send'. Once the watch triggers, one command
    is taken out of the command queue and sent over the channel.

    When the response arrives, the next command is taken out of the queue.
    If there are no more commands, the 'ready-to-send' watch is removed.
    """

    def __init__( self, *args, **kwargs ):
        """
        Initialize.
        """
        VirtualChannel.__init__( self, *args, **kwargs )
        self.q = PeekholeQueue()
        self.installParser()

        self.watchTimeout = None

        self.timeout = kwargs.get( "timeout", DEFAULT_CHANNEL_TIMEOUT )

        logger.info( "%s: Creating channel with timeout = %d seconds", self, self.timeout )

    def installParser( self ):
        """
        Install a low level parser for this channel.

        Override this, if you need to install a special low level parser.
        """
        self.parser = parser.LowlevelAtParser( self._handleResponseToRequest, self._handleUnsolicitedResponse )

    def enqueue( self, data, response_cb=None, error_cb=None, prefixes=None ):
        """
        Enqueue data block for sending over the channel.
        """

        if prefixes is None:
            try:
                prefixes = AUTOPREFIX_CACHE[data]
            except KeyError:
                AUTOPREFIX_CACHE[data] = prefixes = set( AUTOPREFIX.findall( data ) )
                logger.debug( "%s: Autogenerated prefixes for command %s: %s", self, repr(data), prefixes )

        if type( data ) == types.UnicodeType:
            data = str( data )
        self.q.put( ( data, response_cb, error_cb, prefixes ) )
        if not self.connected:
            return
        if self.q.qsize() == 1 and not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend, priority=PRIORITY_RTS )

    def pendingCommands( self ):
        """
        Return the number of pending commands.
        """
        return len( self.q.queue )

    def isWaitingForResponse( self ):
        """
        Return True, when a command is currently waiting for a response.
        Return False, otherwise.
        """
        return self.watchTimeout is not None

    def validPrefixes( self ):
        """
        Return a list of prefixes that are valid for the command in execution.
        """
        if not self.isWaitingForResponse():
            return []

        return self.q.peek()[3]

    def cancelCurrentCommand( self ):
        """
        Cancel the command currently in process.
        """
        if self.watchTimeout is None:
            return
        self._handleCommandCancellation()

    def readyToSend( self ):
        """
        Reimplemented for internal purposes.
        """
        if self.q.empty():
            self.watchReadyToSend = None
            return False

        logger.debug( "%s: sending %d bytes: %s" % ( repr(self), len(self.q.peek()[0]), repr(self.q.peek()[0]) ) )
        self._lowlevelWrite( self.q.peek()[0] ) # 0 = request data
        self.watchTimeout = gobject.timeout_add_seconds( self.timeout, self._handleCommandTimeout )
        return False

    def readyToRead( self, data ):
        """
        Reimplemented for internal purposes.
        """

        # restart timeout //FIXME: only if we were waiting for a response?
        if self.watchTimeout is not None:
            gobject.source_remove( self.watchTimeout )
            self.watchTimeout = gobject.timeout_add_seconds( self.timeout, self._handleCommandTimeout )
        self.parser.feed( data, self.isWaitingForResponse(), self.validPrefixes() )

    def handleUnsolicitedResponse( self, response ):
        """
        Override this to handle an unsolicited response.

        The default implementation does nothing.
        """
        logger.info( "%s: unhandled unsolicited data incoming: %s", self, repr(response) )

    def handleResponseToRequest( self, request, response ):
        """
        Override this to handle a response to a request.

        The default implementation calls the success callback pinned to the request.
        """
        reqstring, ok_cb, error_cb, timeout = request
        if not ok_cb and not error_cb:
            logger.debug( "%s: COMPLETED '%s' => %s" % ( repr(self), reqstring.strip(), response ) )
        else:
            logger.debug( "%s: COMPLETED '%s' => %s" % ( repr(self), reqstring.strip(), response ) )

            try:
                # check whether given callback is a generator
                # if so, advance and give result, if not
                # call it as usual
                if hasattr( ok_cb, "send" ):
                    ok_cb.send( response )
                else:
                    ok_cb( reqstring.strip(), response )
            except Exception, e:
                logger.exception( "(ignoring) unhandled exception in response callback: %s" % e )

    def handleCommandTimeout( self, request ):
        """
        Override this to handle a command timeout.

        The default implementation calls the error callback pinned to the request.
        """
        reqstring, ok_cb, error_cb, prefixes = request
        if not ok_cb and not error_cb:
            logger.debug( "%s: TIMEOUT '%s' => ???" % ( repr(self), reqstring.strip() ) )
        else:
            logger.debug( "%s: TIMEOUT '%s' => ???" % ( repr(self), reqstring.strip() ) )
            error_cb( reqstring.strip(), ( "timeout", self.timeout ) )

    #
    # private API
    #
    def _handleCommandCancellation( self ):
        """
        Called, when the current command should be cancelled.

        According to v25ter, this can be done by sending _any_
        character to the serial line.
        """
        if self.watchTimeout is None:
            logger.warning( "no command to cancel" )
            return
        # we have a timer, so lets stop it
        gobject.source_remove( self.watchTimeout )
        self.watchTimeout = None
        # send EOF to cancel current command
        logger.debug( "%s: sending EOF" % repr(self) )
        self.serial.write( "\x1A" )
        logger.debug( "%s: EOF sent" % repr(self) )
        # We do _not_ erase the current command and send cancellation ACK,
        # otherwise we would get an "unsolicited" OK as response. If for
        # whatever reason we would like to change the semantics, we could do
        # with something like:
        #   request = self.q.get()
        #   reqstring, ok_cb, error_cb, timeout = request
        #   error_cb( reqstring.strip(), ( "cancel", timeout ) )

    def _handleUnsolicitedResponse( self, response ):
        """
        Called from parser, when an unsolicited response has been parsed.
        """
        self.handleUnsolicitedResponse( response )
        return self.isWaitingForResponse() # parser needs to know the current status

    def _handleResponseToRequest( self, response ):
        """
        Called from parser, when a response to a request has been parsed.
        """
        # stop timer
        if self.watchTimeout is not None:
            gobject.source_remove( self.watchTimeout )
            self.watchTimeout = None
        # handle response
        request = self.q.get()
        self.handleResponseToRequest( request, response )
        # relaunch
        if not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend, priority=PRIORITY_RTS )
        return self.isWaitingForResponse() # parser needs to know the current status

    def _handleCommandTimeout( self ):
        """
        Called from mainloop, when a command does not get a response within a certain timeout.

        Here, we need to send an EOF to cancel the current command. If we would not,
        then an eventual response (outside the timeout interval) would be misrecognized
        as an unsolicited response.
        """
        self.watchTimeout = None
        self.serial.write( "\x1A" )
        self.handleCommandTimeout( self.q.get() )
        # relaunch
        if not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend, priority=PRIORITY_RTS )
        return False

#=========================================================================#
class DelegateChannel( QueuedVirtualChannel ):
#=========================================================================#
    """
    This class contains a setDelegate() function that allows convenient
    handling of incoming unsolicited messages.
    """

    def __init__( self, *args, **kwargs ):
        QueuedVirtualChannel.__init__( self, *args, **kwargs )

        self.prefixmap = { '+': 'plus',
                           '%': 'percent',
                           '@': 'at',
                           '/': 'slash',
                           '#': 'hash',
                           '_': 'underscore',
                           '*': 'star',
                           '&': 'ampersand',
                           'C': 'C',
                           'R': 'R',
                           'N': 'N',
                         }
        self.delegate = None

    def setDelegate( self, object ):
        """
        Set a delegate object to which all unsolicited responses are delegated first.
        """
        if self.delegate is not None:
            logger.warning( "delegate already set. Ignoring" )
            return
        self.delegate = object

    def _handleUnsolicitedResponse( self, response ):
        """
        Reimplemented for internal purposes.

        This class changes the semantics of how handleUnsolicitedResponse()
        is getting called. If a delegate is installed, handleUnsolicitedResponse()
        will only be getting called, if no appropriate delegate method can be found.
        """

        data = response[0]

        if self.delegate is None:
            # no delegate installed, hand over to generic handler
            return self.handleUnsolicitedResponse( data )

        if not data[0] in self.prefixmap:
            return False
        if not ':' in data:
            return False
        command, values = data.split( ':', 1 )

        # convert unsolicited command to a method name
        command = command.replace( ' ', '_' ) # no spaces in Python identifiers
        methodname = "%s%s" % ( self.prefixmap[command[0]], command[1:] ) # no special characters

        try:
            method = getattr( self.delegate, methodname )
        except AttributeError:
            # no appropriate handler found, hand over to generic handler
            return self.handleUnsolicitedResponse( data )
        else:
            try:
                if len( response ) == 2:
                    # unsolicited data contains a PDU
                    method( values.strip(), response[1] )
                else:
                    method( values.strip() )
            except Exception, e:
                logger.exception( "(ignoring) unhandled exception in unsolicited response handler: %s" % e )
                return False

        return True # unsolicited response handled OK

#=========================================================================#
class AtCommandChannel( DelegateChannel ):
#=========================================================================#
    """
    This class represents an AT command channel.

    Commands are prefixed according to v25ter. Multiline commands are handled.
    """

    def enqueue( self, command, response_cb=None, error_cb=None, prefixes=None ):
        """
        Enqueue a single line or multiline command. Multiline commands have
        a '\r' (NOT '\r\n') embedded after the first line.
        """
        commands = command.split( '\r', 1 )

        if len( commands ) == 1:
            QueuedVirtualChannel.enqueue( self, "AT%s\r\n" % command, response_cb, error_cb, prefixes )

        elif len( commands ) == 2:
            QueuedVirtualChannel.enqueue( self, "AT%s\r" % commands[0], self.onMultilineCommandResponse, self.onMultilineCommandError, prefixes )
            QueuedVirtualChannel.enqueue( self, "%s\x1A" % commands[1], response_cb, error_cb, prefixes )

    def onMultilineCommandResponse( self, request, response ):
        if response != []:
            logger.warning( "multiline command got bogus response '%s' after first line. pushing ERROR to upper layer" )
            self._handleResponseToRequest( "+EXT I: INTERNAL" )

    def onMultilineCommandError( self, request, error ):
        logger.error( "multiline command got error after first line. pushing ERROR to upper layer" )
        self._handleResponseToRequest( "+EXT I: INTERNAL" )

    # you should not need to call this anymore
    enqueueRaw = QueuedVirtualChannel.enqueue

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    print "no tests written yet :("
