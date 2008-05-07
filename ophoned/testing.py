#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import gobject
import serial
import Queue
import select
import itertools
import fcntl, os

def loggedFunction( fn ):
    """
    This decorator logs the name of a function or, if applicable,
    a method including the classname.
    """
    import inspect
    def logIt( *args, **kwargs ):
        calldepth = len( inspect.stack() )
        try:
            classname = args[0].__class__.__name__
        except AttributeError:
            classname = ""
        print "%s> %s.%s: ENTER" % ( '|...' * calldepth, classname, fn.__name__ )
        result = fn( *args, **kwargs )
        print "%s> %s.%s: LEAVE" % ( '|...' * calldepth, classname, fn.__name__ )
        return result
    return logIt

#=========================================================================#
class VirtualChannel( object ):
#=========================================================================#
    """
    This class represents a virtual multiplexed channel
    over which GSM 07.07 / 07.05 (AT) commands are transported.
    """

    DEBUGLOG = 1

    #
    # public API
    #
    @loggedFunction
    def __init__( self, bus, name=None ):
        """Construct"""
        self.name = name or self.__class__.__name__
        self.bus = bus
        self.connected = False
        self.watchReadyToSend = None
        self.watchReadyToRead = None
        self.timeoutKeepAlive = None

        if VirtualChannel.DEBUGLOG:
            self.debugFile = open( "/tmp/%s.log" % self.name, "w" )

    def _requestChannelPath( self ):
        oMuxer = self.bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        self.iMuxer = dbus.Interface( oMuxer, "org.freesmartphone.GSM.MUX" )
        return self.iMuxer.AllocChannel( self.name )

    @loggedFunction
    def open( self ):
        """
        Allocate a virtual channel and open a serial port.
        Returns True, if successful. False, otherwise.
        """
        assert not self.connected, "already connected"

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

        # ugly hack wrt. modem lazy init... send \r\n until we actually get an OK
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
        #self.serial.flushInput()

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead )
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )
        self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self._hup )
        self.connected = self.serial.isOpen()
        return self.connected

    def launchKeepAlive( self ):
            if self.connected:
                self.timeoutKeepAlive = gobject.timeout_add( 7000, self._modemKeepAlive )
                self._modemKeepAlive()


    def readyToRead( self, data ):
        pass

    def readyToSend( self ):
        pass

    @loggedFunction
    def write( self, data ):
        """
        Write data to the modem.
        """
        self._write( data )

    @loggedFunction
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
    @loggedFunction
    def _hup( self, source, condition ):
        assert source == self.serial.fd, "HUP on bogus source"
        assert condition == gobject.IO_HUP, "HUP on bogus condition"
        self.close()
        # TODO add restart functionality ?

    @loggedFunction
    def _readyToRead( self, source, condition ):
        """Data available"""
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

    @loggedFunction
    def _readyToSend( self, source, condition ):
        """Port ready to send"""
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

    @loggedFunction
    def __del__( self ):
        """Destruct"""
        self.close()

    def _modemKeepAlive( self, *args ):
        if self.connected:
            self.enqueue( "\r\n" )
        return True

#=========================================================================#
class QueuedVirtualChannel( VirtualChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        VirtualChannel.__init__( self, *args, **kwargs )
        self.q = Queue.Queue()

    @loggedFunction
    def enqueue( self, command ):
        self.q.put( "AT%s\r\n" % command )
        if not self.connected:
            return
        if self.q.qsize() == 1 and not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

    @loggedFunction
    def readyToSend( self ):
        if self.q.empty():
            print "(nothing in request queue)"
            return

        print "(sending to port: %s)" % repr(self.q.queue[0])
        if VirtualChannel.DEBUGLOG:
            self.debugFile.write( self.q.queue[0] )
        self.serial.write( self.q.queue[0] )

    @loggedFunction
    def readyToRead( self, data ):
        if self.q.empty():
            print "=> unsolicited message: '%s'" % ( data.strip() )
        else:
            print "=> AT command '%s' received '%s' as response" % ( self.q.get().strip(), data.strip() )
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )

#=========================================================================#
class GenericModem( QueuedVirtualChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        QueuedVirtualChannel.__init__( self, *args, **kwargs )

        self.enqueue('Z') # soft reset
        self.enqueue('E0V1') # echo off, verbose result on
        self.enqueue('+CMEE=2') # report mobile equipment error
        self.enqueue('+CRC=1') # cellular result codes, enable extended format

#=========================================================================#
class UnsolicitedResponseChannel( GenericModem ):
#=========================================================================#

    # idea: put something into the command queue,
    # if the command queue was empty before, it requests
    # the clear to send, then sends a request on every clear-to-send
    # if the queue is empty, disable the watch for clear to send

    def __init__( self, *args, **kwargs ):
        GenericModem.__init__( self, *args, **kwargs )

        self.enqueue('+CREG=2') # enable network registration and location information unsolicited result code
        self.enqueue('+CLIP=1') # calling line identification presentation enable
        self.enqueue('+COLP=1') # connected line identification presentation enable
        self.enqueue('+CCWA=1') # call waiting
        self.enqueue('+CRC=1') # cellular result codes: extended
        self.enqueue('+CSNS=0') # single numbering scheme: voice
        self.enqueue('+CTZU=1') # timezone update
        self.enqueue('+CTZR=1') # timezone reporting

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
    v = GenericModem( bus )
    gobject.threads_init()
    import thread
    thread.start_new_thread( run, () )

    u = UnsolicitedResponseChannel( bus )

    import atexit
    atexit.register( cleanup, () )
