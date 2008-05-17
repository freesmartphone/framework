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
        To work around this, we send '\x1a\r\n' until we actually get an
        'OK' from the modem. We try this for 5 times, then we reopen
        the serial line. If after 10 times we still have no response,
        we assume that the modem is broken and fail.
        """
        for i in itertools.count():
            print "(modem init... try #%d)" % ( i+1 )
            select.select( [], [self.serial.fd], [], 0.5 )
            self.serial.write( "\x1a\r\n" )
            r, w, x = select.select( [self.serial.fd], [], [], 0.5 )
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
                if "OK" in ok or "AT" in ok:
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
        self.mainloop.quit()
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
        print "(%s: got %d bytes: %s)" % ( repr(self), len(data), repr(data) )
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

    @logged
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
        """Return the number of pending commands."""
        return len( self.q.queue )

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
        commands = command.split( '\r',1 )
        if len( commands ) == 1:
            QueuedVirtualChannel.enqueue( self, "AT%s\r\n" % command, response_cb, error_cb, timeout )
        elif len( commands ) == 2:
            QueuedVirtualChannel.enqueue( self, "AT%s\r" % commands[0], None, None, None )
            QueuedVirtualChannel.enqueue( self, "%s\x1A" % commands[1], response_cb, error_cb, timeout )

    enqueueRaw = QueuedVirtualChannel.enqueue

#=========================================================================#
class GenericModemChannel( AtCommandChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        QueuedVirtualChannel.__init__( self, *args, **kwargs )

        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=1') # report mobile equipment errors in numerical format
        self.enqueue('+CRC=1') # cellular result codes, enable extended format

        # self.enqueue('+CPMS="SM","SM","SM"') # preferred message storage: sim memory for mo,mt,bm
        self.enqueue('+CMGF=1') # meesage format: pdu mode sms disable, text
        self.enqueue('+CSCS="8859-1"') # character set conversion
        self.enqueue('+CSDH=1') # show text mode parameters: show values

    def launchKeepAlive( self, timeout, command ):
        """Setup a keep-alive timeout."""
        self.keepAliveCommand = command
        self.timeoutKeepAlive = gobject.timeout_add_seconds( timeout, self._modemKeepAlive )
        self._modemKeepAlive()

    def _modemKeepAlive( self, *args ):
        """Send a keep-alive-command to the modem to keep it from falling asleep."""
        if self.connected and ( self.keepAliveCommand is not None ):
            self.enqueue( self.keepAliveCommand )
        return True

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

        self.prefixmap = { '+': 'plus',
                           '%': 'percent',
                           '@': 'at',
                           '/': 'slash',
                           '#': 'hash',
                           '_': 'underscore' }

        self.delegate = None

    @logged
    def handleUnsolicitedResponse( self, data ):
        if not data[0] in self.prefixmap:
            return False
        if not ':' in data:
            return False
        command, values = data.split( ':', 1 )

        if not self.delegate:
            return False

        methodname = "%s%s" % ( self.prefixmap[command[0]], command[1:] )

        try:
            method = getattr( self.delegate, methodname )
        except AttributeError:
            return False
        else:
            method( values )

        return True

    def setDelegate( self, object ):
        """
        Set a delegate object to which all unsolicited responses are delegated.
        """
        assert self.delegate is None, "delegate already set"
        self.delegate = object

#=========================================================================#
# testing stuff here
#=========================================================================#
def error( r, o ):
    print r, o

def queryModem( command ):
    def genfunc():
        genfunc.result = (yield)

    g = genfunc()
    g.next()
    misc.enqueue( command, g, error )
    return g

def launchReadThread( serport ):
    import thread
    thread.start_new_thread( reader, (serport,) )

if __name__ == "__main__":
    import dbus, sys, thread, atexit

    def run():
        import dbus.mainloop.glib
        dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
        run.mainloop = gobject.MainLoop()
        run.mainloop.run()

    def cleanup( *args, **kwargs ):
        run.mainloop.quit()

    def reader( serport ):
        while True:
            data = serport.read()
            print ">>>>>>>>>>>>> GOT %d bytes '%s'" % ( len(data), repr(data) )

    if not hasattr( gobject, "timeout_add_seconds" ):
        def timeout_add_seconds( seconds, callback ):
            return gobject.timeout_add( seconds*1000, callback )
        gobject.timeout_add_seconds = timeout_add_seconds

    bus = dbus.SystemBus()
    misc = GenericModemChannel( bus, timeout=5 )
#    call = GenericModemChannel( bus, timeout=10 )
#    unsol = UnsolicitedResponseChannel( bus )
#    unsol.launchKeepAlive( 8, "" )
#    call.open()
#    unsol.open()
    misc.open()

    gobject.threads_init()
    if len( sys.argv ) == 1:
        thread.start_new_thread( run, () )

    atexit.register( cleanup, () )
