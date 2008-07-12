#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: channel

This module provides communication channel abstractions that
transport their data over a (virtual) serial line.
"""

from ogsmd.gsm.decor import logged
import parser

import gobject # pygobject

import serial # pyserial
import Queue, fcntl, os # stdlib

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

    DEBUGLOG = 0

    #
    # public API
    #
    @logged
    def __init__( self, pathfactory, name=None, **kwargs ):
        """Construct"""
        self.pathfactory = pathfactory
        self.name = name or self.__class__.__name__
        self.connected = False
        self.watchReadyToSend = None
        self.watchReadyToRead = None
        self.serial = None

        if VirtualChannel.DEBUGLOG:
            self.debugFile = open( "/tmp/%s.log" % self.name, "w" )

    @logged
    def open( self, path=None ):
        """
        Allocate a channel and opens a serial port.
        Returns True, if successful. False, otherwise.
        """
        assert not self.connected, "already connected"

        # gather path
        path = self.pathfactory( self.name )
        if path is None or path == "":
            return False

        # set up serial port object and open it
        print "(%s: using modem path '%s')" % ( repr(self), path )
        self.serial = serial.Serial()
        self.serial.port = str( path )
        self.serial.baudrate = 115200
        self.serial.rtscts = True
        self.serial.xonxoff = False
        self.serial.bytesize = serial.EIGHTBITS
        self.serial.parity = serial.PARITY_NONE
        self.serial.stopbits = serial.STOPBITS_ONE
        self.serial.timeout = None
        self.serial.open()
        if not self.serial.isOpen():
            return False

        # nonblocking
        # fcntl.fcntl( self.serial.fd, fcntl.F_SETFL, os.O_NONBLOCK )

        if not self._hookLowLevelInit():
            return False

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead )
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )
        self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self._hup )
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

    @logged
    def suspend( self, ok_callback, error_callback ):
        """
        Called when the channel needs to be prepared for a suspend.

        The default implementation does nothing but call the ok_callback
        """
        ok_callback( self )

    @logged
    def resume( self, ok_callback, error_callback ):
        """
        Called when the channel needs to reinit after resume.

        The default implementation does nothing but call the ok_callback
        """
        ok_callback( self )

    @logged
    def write( self, data ):
        """Write data to the modem."""
        self._write( data )

    @logged
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
        if self.serial.isOpen():
            self.serial.close()
        self.connected = self.serial.isOpen()
        return not self.connected

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

    #
    # private API
    #
    @logged
    def _hup( self, source, condition ):
        """Called, if there is a HUP condition on the source."""
        assert source == self.serial.fd, "HUP on bogus source"
        assert condition == gobject.IO_HUP, "HUP on bogus condition"
        print( "%s: HUP on socket, trying to recover" % repr(self) )
        self.close()
        time.sleep( 1 )
        self.open()
        return True

    @logged
    def _readyToRead( self, source, condition ):
        """Called, if data is available on the source."""
        assert source == self.serial.fd, "ready to read on bogus source"
        assert condition == gobject.IO_IN, "ready to read on bogus condition"

        self._hookPreReading()

        try:
            inWaiting = self.serial.inWaiting()
        except IOError:
            inWaiting = 0
        data = self.serial.read( inWaiting )
        print "(%s: got %d bytes from %s: %s)" % ( repr(self), len(data), self.serial.port, repr(data) )
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( data )
        self.readyToRead( data )

        self._hookPostReading()
        return True

    @logged
    def _readyToSend( self, source, condition ):
        """Called, if source is ready to receive data."""
        assert source == self.serial.fd, "ready to write on bogus source"
        assert condition == gobject.IO_OUT, "ready to write on bogus condition"


        self._hookPreSending()
        self.readyToSend()
        self.watchReadyToSend = None
        self._hookPostSending()

        return False

    def _slowButCorrectWrite( self, data ):
        """
        Write data to the serial port.

        Implementation Note: This does not immediately write the data, but rather
        set up a watch that gets triggered once the serial port is ready to acccept
        written data. If this _may_ turn out to be too heavyweight (because of the
        overhead of creating the lambda function and the additional function call),
        then you better set __USE_FAST_WRITE = 1 and make it directly use serial.write()
        """
        gobject.io_add_watch( self.serial.fd, gobject.IO_OUT,
        lambda source, condition, serial=self.serial, data=data: self.serial.write( data ) is not None )

    __USE_FAST_WRITE = 0
    if __USE_FAST_WRITE:
        _write = self.serial.write
    else:
        _write = _slowButCorrectWrite

    @logged
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

        self.parser = parser.LowlevelAtParser( self._handleResponseToRequest, self._handleUnsolicitedResponse )

        self.watchTimeout = None
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
        else:
            self.timeout = 5 # default timeout in seconds

        print "(%s: Creating channel with timeout = %d seconds)" % ( repr(self), self.timeout )

    def enqueue( self, data, response_cb=None, error_cb=None, timeout=None ):
        """
        Enqueue data block for sending over the channel.
        """
        self.q.put( ( data, response_cb, error_cb, timeout or self.timeout ) )
        if not self.connected:
            return
        if self.q.qsize() == 1 and not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

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

    def cancelCurrentCommand( self ):
        """
        Cancel the command currently in process.
        """
        if self.watchTimeout is None:
            return
        self._handleCommandCancellation()

    @logged
    def readyToSend( self ):
        """
        Reimplemented for internal purposes.
        """
        if __debug__: print "(%s queue is: %s)" % ( repr(self), repr(self.q.queue) )
        if self.q.empty():
            if __debug__: print "(%s: nothing in request queue)" % repr(self)
            self.watchReadyToSend = None
            return False

        print "(%s: sending %d bytes to %s: %s)" % ( repr(self), len(self.q.peek()[0]), self.serial.port, repr(self.q.peek()[0]) )
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( self.q.peek()[0] ) # channel data

        self.serial.write( self.q.peek()[0] ) # channel data
        if self.q.peek()[3]: # channel timeout
            self.watchTimeout = gobject.timeout_add_seconds( self.q.peek()[3], self._handleCommandTimeout )
        return False

    @logged
    def readyToRead( self, data ):
        """
        Reimplemented for internal purposes.
        """
        self.parser.feed( data, not self.q.empty() )

    def handleUnsolicitedResponse( self, response ):
        """
        Override this to handle an unsolicited response.

        The default implementation does nothing.
        """
        print "(%s: unsolicited data incoming: %s)" % ( repr(self), response )

    def handleResponseToRequest( self, request, response ):
        """
        Override this to handle a response to a request.

        The default implementation calls the success callback pinned to the request.
        """
        reqstring, ok_cb, error_cb, timeout = request
        if not ok_cb and not error_cb:
            print "(%s: COMPLETED '%s' => %s)" % ( repr(self), reqstring.strip(), response )
        else:
            print "(%s: COMPLETED '%s' => %s)" % ( repr(self), reqstring.strip(), response )

            # check whether given callback is a generator
            # if so, advance and give result, if not
            # call it as usual
            if hasattr( ok_cb, "send" ):
                ok_cb.send( response )
            else:
                ok_cb( reqstring.strip(), response )

    def handleCommandTimeout( self, request ):
        """
        Override this to handle a command timeout.

        The default implementation calls the error callback pinned to the request.
        """
        reqstring, ok_cb, error_cb, timeout = request
        if not ok_cb and not error_cb:
            print "(%s: TIMEOUT '%s' => ???)" % ( repr(self), reqstring.strip() )
        else:
            print "(%s: TIMEOUT '%s' => ???)" % ( repr(self), reqstring.strip() )
            error_cb( reqstring.strip(), ( "timeout", timeout ) )

    #
    # private API
    #

    @logged
    def _handleCommandCancellation( self ):
        """
        Called, when the current command should be cancelled.

        According to v25ter, this can be done by sending _any_
        character to the serial line.
        """
        assert self.watchTimeout is not None, "no command to cancel"
        # we have a timer, so lets stop it
        gobject.source_remove( self.watchTimeout )
        self.watchTimeout = None
        # send EOF to cancel current command
        print "(%s: sending EOF)" % repr(self)
        self.serial.write( "\x1A" )
        print "(%s: EOF sent)" % repr(self)
        # We do _not_ erase the current command and send cancellation ACK,
        # otherwise we would get an "unsolicited" OK as response. If for
        # whatever reason we want to change the semantics, we could do
        # with something like:
        #   request = self.q.get()
        #   reqstring, ok_cb, error_cb, timeout = request
        #   error_cb( reqstring.strip(), ( "cancel", timeout ) )

    @logged
    def _handleUnsolicitedResponse( self, response ):
        """
        Called, when an unsolicited response has been parsed.
        """
        self.handleUnsolicitedResponse( response )

    @logged
    def _handleResponseToRequest( self, response ):
        """
        Called, when a response to a request has been parsed.
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
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

    @logged
    def _handleCommandTimeout( self ):
        """
        Called, when a command does not get a response within a certain timeout.

        Here, we need to send an EOF to cancel the current command. If we would not,
        then an eventual response (outside the timeout interval) would be misrecognized
        as an unsolicited response.
        """
        self.serial.write( "\x1A" )
        self.handleCommandTimeout( self.q.get() )

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
                         }
        self.delegate = None

    def setDelegate( self, object ):
        """
        Set a delegate object to which all unsolicited responses are delegated first.
        """
        assert self.delegate is None, "delegate already set"
        self.delegate = object

    @logged
    def _handleUnsolicitedResponse( self, data ):
        """
        Reimplemented for internal purposes.

        This class changes the semantics of how handleUnsolicitedResponse()
        is getting called. If a delegate is installed, handleUnsolicitedResponse()
        will only be getting called, if no appropriate delegate method can be found.
        """

        if not data[0] in self.prefixmap:
            return False
        if not ':' in data:
            return False
        command, values = data.split( ':', 1 )

        if not self.delegate:
            # no delegate installed, hand over to generic handler
            return self.handleUnsolicitedResponse( data )

        methodname = "%s%s" % ( self.prefixmap[command[0]], command[1:] )

        try:
            method = getattr( self.delegate, methodname )
        except AttributeError:
            # no appropriate handler found, hand over to generic handler
            return self.handleUnsolicitedResponse( data )
        else:
            method( values.strip() )

        return True # unsolicited response handled OK

#=========================================================================#
class AtCommandChannel( DelegateChannel ):
#=========================================================================#
    """
    This class represents an AT command channel.

    Commands are prefixed according to v25ter. Multiline commands are handled.
    """
    @logged
    def enqueue( self, command, response_cb=None, error_cb=None, timeout=None ):
        """
        Enqueue a single line or multiline command. Multiline commands have
        a '\r' (NOT '\r\n') embedded after the first line.
        """
        commands = command.split( '\r', 1 )
        if len( commands ) == 1:
            QueuedVirtualChannel.enqueue( self, "AT%s\r\n" % command, response_cb, error_cb, timeout )
        elif len( commands ) == 2:
            QueuedVirtualChannel.enqueue( self, "AT%s\r" % commands[0], None, None, None )
            QueuedVirtualChannel.enqueue( self, "%s\x1A" % commands[1], response_cb, error_cb, timeout )
        else:
            assert False, "your python interpreter is broken"

    # you should not need to call this
    enqueueRaw = QueuedVirtualChannel.enqueue

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    print "no tests written yet :("
