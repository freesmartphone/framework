#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import gobject

import serial

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

class VirtualChannel( object ):
    """
    This class represents a virtual multiplexed channel
    over which GSM 07.07 / 07.05 (AT) commands are transported.
    """

    #
    # public API
    #
    @loggedFunction
    def __init__( self, bus, name=None ):
        """Construct"""
        self.name = name or self.__class__.__name__
        self.bus = bus
        self.connected = False
        self.watchReadyToSend = 0
        self.watchReadyToRead = 0

    @loggedFunction
    def open( self ):
        """
        Allocate a virtual channel and open a serial port.
        Returns True, if successful. False, otherwise.
        """
        assert not self.connected, "already connected"

        # allocate channel with muxer, gather path
        oMuxer = self.bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        self.iMuxer = dbus.Interface( oMuxer, "org.freesmartphone.GSM.MUX" )
        path = self.iMuxer.AllocChannel( self.name )
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

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self._readyToRead )
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self._readyToSend )
        self.connected = self.serial.isOpen()
        return self.connected

    def readyToRead( self ):
        pass

    def readyToSend( self ):
        pass

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
    def _readyToRead( self, source, condition ):
        """Data available"""
        assert source == self.serial.fd, "dataReady on bogus source"
        assert condition == gobject.IO_IN, "dataReady on bogus condition"
        data = self.serial.readline()
        #data = self.serial.readlines()
        print "got %d bytes: %s" % ( len(data), repr(data) )
        # readyToRead( data )
        return True

    @loggedFunction
    def _readyToSend( self, source, condition ):
        """Port ready to send"""
        assert source == self.serial.fd, "dataReady on bogus source"
        assert condition == gobject.IO_OUT, "dataReady on bogus condition"
        self.readyToSend()
        return False

    def _SlowButCorrectWrite( self, data ):
        """
        Write data to the serial port.

        Implementation Note: This does not immediately write the data, but rather
        set up a watch that gets triggered once the serial port is ready to acccept
        written data. If this _may_ turn out to be too heavyweight (because of the
        overhead of creating the lambda function and the additional function call),
        then you better set __USE_FAST_WRITE = 1 and make it directly use serial.write()
        """
        self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT,
        lambda source, condition, serial=self.serial, data=data: self.serial.write( data ) is not None )

    __USE_FAST_WRITE = 0
    if __USE_FAST_WRITE:
        _write = self.serial.write
    else:
        _write = _SlowButCorrectWrite

    @loggedFunction
    def __del__( self ):
        """Destruct"""
        self.close()

class UnsolicitedResponseChannel( VirtualChannel ):
    pass

def run():
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop( set_as_default=True )
    mainloop = gobject.MainLoop()
    mainloop.run()

if __name__ == "__main__":
    import dbus
    v = VirtualChannel( dbus.SystemBus() )
    gobject.threads_init()
    import thread
    thread.start_new_thread( run, () )
