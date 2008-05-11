#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import dbus
import gobject
import serial
import Queue
import select
import itertools
import fcntl, os
import parser
from decor import logged

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

    This class supports two modes:
    * standalone (talking over a serial port of the modem)
    * multiplexed (talking over a multiplexed virtual channel to the modem)
    """

    DEBUGLOG = 1

    #
    # public API
    #
    @logged
    def __init__( self, bus, name=None, **kwargs ):
        """Construct"""
        self.name = name or self.__class__.__name__
        self.bus = bus
        self.connected = False
        self.watchReadyToSend = None
        self.watchReadyToRead = None
        self.timeoutKeepAlive = None

        if VirtualChannel.DEBUGLOG:
            self.debugFile = open( "/tmp/%s.log" % self.name, "w" )

    @logged
    def open( self, path="MUX" ):
        """
        Allocate a virtual channel and open a serial port.
        Returns True, if successful. False, otherwise.
        """
        assert not self.connected, "already connected"

        if path == "MUX":
            path = self._requestChannelPath()
        if not path:
            return False

        # set up serial port object and open it
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

        if not self._lowlevelInit():
            return False

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead )
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )
        self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self._hup )
        self.connected = self.serial.isOpen()
        return self.connected

    def launchKeepAlive( self ):
        """Setup a keep-alive timeout."""
        if self.connected:
            self.timeoutKeepAlive = gobject.timeout_add( 7000, self._modemKeepAlive )
            self._modemKeepAlive()


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
        if self.timeoutKeepAlive:
            gobject.source_remove( self.timeoutKeepAlive )
        if self.watchReadyToSend:
            gobject.source_remove( self.watchReadyToSend )
        if self.watchReadyToRead:
            gobject.source_remove( self.watchReadyToRead )
        if self.serial.isOpen():
            self.serial.close()
        self.connected = self.serial.isOpen()
        return not self.connected

    #
    # private API
    #
    def _requestChannelPath( self ):
        """Allocate a new channel from the MUXer."""
        oMuxer = self.bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        self.iMuxer = dbus.Interface( oMuxer, "org.freesmartphone.GSM.MUX" )
        return self.iMuxer.AllocChannel( self.name )

    @logged
    def _lowlevelInit( self ):
        """
        Low level initialization of channel.

        This is actually an ugly hack which is unfortunately
        necessary since some multiplexers in modems have problems
        wrt. to initialization (swallowing first bunch of commands etc.)
        To work around this, we send \r\n until we actually get an
        'OK' from the modem. We try this for 5 times, then we reopen
        the serial line. If after 10 times, we still have no response,
        we assume that the modem is broken and fail.
        """
        for i in itertools.count():
            print "(modem init... try #%d)" % ( i+1 )
            select.select( [], [self.serial.fd], [], 0.5 )
            print "(select1 returned)"
            self.serial.write( "\r\n" )
            r, w, x = select.select( [self.serial.fd], [], [], 0.5 )
            print "(select2 returned)"
            if r:
                try:
                    buf = self.serial.inWaiting()
                except:
                    self.serial.close()
                    path = self._requestChannelPath()
                    if not path:
                        return False
                    self.serial.port = str( path )
                    self.serial.open()
                    buf = self.serial.inWaiting()
                ok = self.serial.read(buf).strip()
                print "read:", repr(ok)
                if ok.startswith( "OK" ) or ok.startswith( "AT" ):
                    break
            print "(modem not responding)"
            if i == 5:
                print "(reopening modem)"
                self.serial.close()
                path = self._requestChannelPath()
                if not path:
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                print "(giving up)"
                self.serial.close()
                return False
        print "(modem responding)"
        self.serial.flushInput()
        return True

    @logged
    def _hup( self, source, condition ):
        """Called, if there is a HUP condition on the source."""
        assert source == self.serial.fd, "HUP on bogus source"
        assert condition == gobject.IO_HUP, "HUP on bogus condition"
        self.close()
        # TODO add restart functionality ?

    @logged
    def _readyToRead( self, source, condition ):
        """Called, if data is available on the source."""
        assert source == self.serial.fd, "ready to read on bogus source"
        assert condition == gobject.IO_IN, "ready to read on bogus condition"
        try:
            inWaiting = self.serial.inWaiting()
        except IOError:
            inWaiting = 0
        data = self.serial.read( inWaiting )
        print "got %d bytes: %s" % ( len(data), repr(data) )
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( data )
        self.readyToRead( data )
        return True

    @logged
    def _readyToSend( self, source, condition ):
        """Called, if source is ready to receive data."""
        assert source == self.serial.fd, "ready to write on bogus source"
        assert condition == gobject.IO_OUT, "ready to write on bogus condition"
        self.readyToSend()
        self.watchReadyToSend = None
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

    def _modemKeepAlive( self, *args ):
        """Send a carriage-return to the modem to keep it from falling asleep."""
        if self.connected:
            self.enqueue( "\r\n" )
        return True

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
            self.timeout = 5000 # 5 seconds default

    @logged
    def enqueue( self, data, response_cb=None, error_cb=None ):
        """
        Enqueue data block for sending over the channel.
        """
        self.q.put( ( data, response_cb, error_cb ) )
        if not self.connected:
            return
        if self.q.qsize() == 1 and not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

    def pendingCommands( self ):
        """Returns number of pending commands."""
        return len( self.q.queue )

    @logged
    def readyToSend( self ):
        """Reimplemented for internal purposes."""
        if self.q.empty():
            print "(nothing in request queue)"
            self.watchReadyToSend = None
            return False

        print "(sending to port: %s)" % repr(self.q.peek())
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( self.q.peek()[0] )
        self.serial.write( self.q.peek()[0] )
        self.watchTimeout = gobject.timeout_add( self.timeout, self._handleCommandTimeout )
        return False

    @logged
    def readyToRead( self, data ):
        """Reimplemented for internal purposes."""
        self.parser.feed( data, not self.q.empty() )

    @logged
    def _handleUnsolicitedResponse( self, response ):
        self.handleUnsolicitedResponse( response )

    @logged
    def _handleResponseToRequest( self, response ):
        # stop timer
        assert self.watchTimeout, "timeout not set"
        gobject.source_remove( self.watchTimeout )
        self.watchTimeout = None
        # handle response
        self.handleResponseToRequest( self.q.get(), response )
        # relaunch
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

    @logged
    def _handleCommandTimeout( self ):
        self.handleCommandTimeout( self.q.get() )

    def handleUnsolicitedResponse( self, response ):
        print "(unsolicited data incoming: %s)" % response

    def handleResponseToRequest( self, request, response ):
        reqstring, ok_cb, error_cb = request
        if not ok_cb and not error_cb:
            print "(COMPLETED '%s' => %s)" % ( reqstring.strip(), response )
        else:
            ok_cb( reqstring.strip(), response )

    def handleCommandTimeout( self, request ):
        reqstring, ok_cb, error_cb = request
        if not ok_cb and not error_cb:
            print "(TIMEOUT '%s' => ???)" % ( reqstring.strip(), request )
        else:
            error_cb( reqstring.strip(), "modem timeout: %d" % self.timeout )

#=========================================================================#
class AtCommandChannel( QueuedVirtualChannel ):
#=========================================================================#
    @logged
    def enqueue( self, command, response_cb=None, error_cb=None ):
        # self.q.put( "AT%s\r\n" % command )
        # send \r\n beforehand?
        self.q.put( ( ( "AT%s\r\n" % command ), response_cb, error_cb ) )
        if not self.connected:
            return
        if not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

#=========================================================================#
class GenericModemChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        QueuedVirtualChannel.__init__( self, *args, **kwargs )

        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=2') # report mobile equipment error
        self.enqueue('+CRC=1') # cellular result codes, enable extended format

#=========================================================================#
class UnsolicitedResponseChannel( GenericModemChannel ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        GenericModemChannel.__init__( self, *args, **kwargs )

        self.enqueue('+CREG=2') # enable network registration and location information unsolicited result code
        self.enqueue('+CLIP=1') # calling line identification presentation enable
        self.enqueue('+COLP=1') # connected line identification presentation enable
        self.enqueue('+CCWA=1') # call waiting
        self.enqueue('+CRC=1') # cellular result codes: extended
        self.enqueue('+CSNS=0') # single numbering scheme: voice
        self.enqueue('+CTZU=1') # timezone update
        self.enqueue('+CTZR=1') # timezone reporting

        if "callback" in kwargs:
            self.callback = kwargs["callback"]
        else:
            self.callback = self

        self.prefixmap = { '+': 'plus', '%': 'percent', '@': 'at', '/': 'slash', '#': 'hash' }

    # FIXME: Consider chain of command pattern here when handling AT responses
    @logged
    def handleUnsolicitedResponse( self, data ):
        if not data.startswith( '+' ):
            return False
        if not ':':
            return False
        command, values = data.split( ':', 1 )

        methodname = "%s%s" % ( self.prefixmap[command[0]], command[1:] )

        if not hasattr( self.callback, methodname ):
            return False

        getattr( self.callback, methodname )( values )
        return True

    def plusCREG( self, values ):
        print "REGISTRATION STATUS:", values

def run():
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop( set_as_default=True )
    run.mainloop = gobject.MainLoop()
    run.mainloop.run()

def cleanup( *args, **kwargs ):
    run.mainloop.quit()

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    a = GenericModemChannel( bus, timeout=5000 )
    b = GenericModemChannel( bus, timeout=10000 )
    u = UnsolicitedResponseChannel( bus )

    gobject.threads_init()
    import thread
    thread.start_new_thread( run, () )

    import atexit
    atexit.register( cleanup, () )
