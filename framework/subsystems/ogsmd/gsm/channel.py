#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: channel

This module contains communication channel abstractions that
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
    def peek( self ):
        if self.empty():
            return None
        else:
            return self.queue[0]

#=========================================================================#
class VirtualChannel( object ):
#=========================================================================#
    """
    This class represents a serial channel
    over which GSM 07.07 / 07.05 (AT) commands are transported.
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
        print "(%s: got %d bytes: %s)" % ( repr(self), len(data), repr(data) )
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
        """Construct."""
        VirtualChannel.__init__( self, *args, **kwargs )
        self.q = PeekholeQueue()

        self.parser = parser.LowlevelAtParser( self._handleResponseToRequest, self._handleUnsolicitedResponse )

        self.watchTimeout = None
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
        else:
            self.timeout = 5 # default timeout in seconds

        if "wakeup" in kwargs:
            self.wakeup = kwargs["wakeup"]
        else:
            self.wakeup = None # no wakeup necessary (default)

        print "(%s: Creating channel with timeout = %d seconds)" % ( repr(self), self.timeout )

    def enqueue( self, data, response_cb=None, error_cb=None, timeout=None ):
        """
        Enqueue data block for sending over the channel.
        """
        self.q.put( ( data, response_cb, error_cb, timeout or self.timeout ) )
        if not self.connected:
            return
        if self.q.qsize() == 1 and not self.watchReadyToSend:
            if self.wakeup:
                self._lowlevelInit()
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
        """Reimplemented for internal purposes."""
        print "(%s queue is: %s)" % ( repr(self), repr(self.q.queue) )
        if self.q.empty():
            print "(%s: nothing in request queue)" % repr(self)
            self.watchReadyToSend = None
            return False

        print "(%s: sending to port: %s)" % ( repr(self), repr(self.q.peek()[0]) )
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( self.q.peek()[0] ) # channel data

        self.serial.write( self.q.peek()[0] ) # channel data
        if self.q.peek()[3]: # channel timeout
            self.watchTimeout = gobject.timeout_add_seconds( self.q.peek()[3], self._handleCommandTimeout )
        return False

    @logged
    def readyToRead( self, data ):
        """Reimplemented for internal purposes."""
        self.parser.feed( data, not self.q.empty() )

    @logged
    def _handleCommandCancellation( self ):
        assert self.watchTimeout is not None, "no command to cancel"
        # stop timer
        gobject.source_remove( self.watchTimeout )
        self.watchTimeout = None
        # send EOF to cancel current command
        print "sending EOF"
        self.serial.write( "\x1A" )
        # erase command and send cancellation ACK
        # FIXME should actually NOT erase the command from the queue, otherwise we
        # get an unsolicited 'OK' as response.
        print "EOF sent"

        #request = self.q.get()
        #reqstring, ok_cb, error_cb, timeout = request
        #error_cb( reqstring.strip(), ( "cancel", timeout ) )

    @logged
    def _handleUnsolicitedResponse( self, response ):
        self.handleUnsolicitedResponse( response )

    @logged
    def _handleResponseToRequest( self, response ):
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
        # send EOF to cancel the current command. If we would not, then a
        # response out of the timeout interval would be misrecognized
        # as an unsolicited response.
        self.serial.write( "\x1A" )
        self.handleCommandTimeout( self.q.get() )

    def handleUnsolicitedResponse( self, response ):
        print "(%s: unsolicited data incoming: %s)" % ( repr(self), response )

    def handleResponseToRequest( self, request, response ):
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
        reqstring, ok_cb, error_cb, timeout = request
        if not ok_cb and not error_cb:
            print "(%s: TIMEOUT '%s' => ???)" % ( repr(self), reqstring.strip() )
        else:
            print "(%s: TIMEOUT '%s' => ???)" % ( repr(self), reqstring.strip() )
            error_cb( reqstring.strip(), ( "timeout", timeout ) )

#=========================================================================#
class AtCommandChannel( QueuedVirtualChannel ):
#=========================================================================#
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

    enqueueRaw = QueuedVirtualChannel.enqueue

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    print "no tests written yet :("
