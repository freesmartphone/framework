#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon - Parse NMEA/UBX data

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from framework.config import config

import os
import sys
import serial
import socket
import gobject

import logging
logger = logging.getLogger('ogpsd')

class GPSChannel( object ):
    """A GPS Channel :-)"""
    def __init__( self, path=None ):
        self.callback = None
        self.debugChannel = None

    def setDebugChannel( self, debugChannel ):
        self.debugChannel = debugChannel
        self.debugChannel.setCallback( self.send )

    def initializeChannel( self ):
        pass

    def shutdownChannel( self ):
        pass

    def suspendChannel( self ):
        self.shutdownChannel()

    def resumeChannel( self ):
        self.initializeChannel()

    def setCallback( self, callback ):
        self.callback = callback

    def send( self, stream ):
        raise Exception( "Not implemented" )

class UDPChannel ( GPSChannel ):
    """Generic UDP reader"""

    def __init__( self, path ):
        super(UDPChannel, self).__init__()
        logger.debug("UDPChannel opens port %s" % path)
        if ":" in path:
            self.host, self.port = path.split( ":" )
            self.port = int( self.port )
        else:
            self.host = ""
            self.port = int( path )
        self.s = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        self.s.bind( ("", self.port) )
        self.s.setblocking(False)
        self.datapending = ""
        self.watchReadyToRead = gobject.io_add_watch( self.s.makefile(), gobject.IO_IN, self.readyToRead )
        self.watchReadyToSend = None

    def readyToRead( self, source, condition ):
        data = self.s.recv(1024)
        if self.callback:
            self.callback(data)
        return True

    def readyToSend( self, source, condition ):
        if self.host:
            self.s.sendto( self.datapending, (self.host, self.port) )
        self.datapending = ""
        self.watchReadyToSend = None
        return False

    def send( self, stream ):
        self.datapending = self.datapending + stream
        if not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.s.makefile(), gobject.IO_OUT, self.readyToSend )

class GllinChannel( UDPChannel ):
    """UDP reader for GTA01, takes care of starting and stopping gllin"""

    def __init__( self, path="/etc/init.d/gllin" ):
        super( GllinChannel, self ).__init__( "6000" )
        self.gllin = path

    def initializeChannel( self ):
        os.system(self.gllin + " start")

    def shutdownChannel( self ):
        os.system(self.gllin + " stop")

class FileChannel ( GPSChannel ):
    """File reader, for gta01, gllin"""

    def __init__(self, path):
        super(FileChannel, self).__init__()
        logger.debug("FileChannel opens %s" % path)
        self.path = path

    def initializeChannel( self ):
        self.fd = os.open(self.path, os.O_NONBLOCK + os.O_RDONLY)
        self.watchReadyToRead = gobject.io_add_watch( self.fd, gobject.IO_IN, self.readyToRead )

    def shutdownChannel( self ):
        gobject.source_remove( self.watchReadyToRead )
        os.close( self.fd )

    def readyToRead( self, source, condition ):
        data_array = []
        try:
            while True:
                data_array.append(os.read(self.fd, 1024))
        except OSError:
            pass
        if len(data_array) == 1:
            data = data_array[0] # shortcut for common case
        else:
            data = ''.join(data_array)
        if self.callback:
            self.callback(data)

        return True
    def send( self, stream ):
        logger.debug( "Tried to send data to a FileChannel, ignoring" )

class SerialChannel( GPSChannel ):
    """Serial reader"""

    def __init__( self, path, rtscts = False):
        super(SerialChannel, self).__init__()

        # set up serial port object and open it
        self.serial = serial.Serial()
        self.serial.port = path
        self.serial.baudrate = config.getValue( "ogpsd.serialchannel", "baudrate", 9600)
        self.serial.rtscts = rtscts
        self.serial.xonxoff = False
        self.serial.bytesize = serial.EIGHTBITS
        self.serial.parity = serial.PARITY_NONE
        self.serial.stopbits = serial.STOPBITS_ONE
        self.serial.timeout = None
        self.datapending = ""
        self.watchReadyToRead = None
        self.watchReadyToSend = None

    def initializeChannel( self ):
        self.serial.open()

        assert self.serial.isOpen(), "Failure opening device"

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self.readyToRead )
        #self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self.readyToSend )
        self.watchReadyToSend = None
        # self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self.hup )

    def shutdownChannel( self ):
        if self.watchReadyToRead:
            gobject.source_remove( self.watchReadyToRead )
            self.watchReadyToRead = None
        if self.watchReadyToSend:
            gobject.source_remove( self.watchReadyToSend )
            self.watchReadyToSend = None
        self.serial.close()
        self.datapending = ""

    def readyToRead( self, source, condition ):
        """Called, if data is available on the source."""
        assert source == self.serial.fd, "ready to read on bogus source"
        assert condition == gobject.IO_IN, "ready to read on bogus condition"

        try:
            inWaiting = self.serial.inWaiting()
        except IOError:
            inWaiting = 0

        data = self.serial.read( inWaiting )

        if self.debugChannel:
            self.debugChannel.send( data )
        if self.callback:
            self.callback( data )

        return True

    def readyToSend( self, source, condition ):
        """Called, if source is ready to receive data."""
        assert source == self.serial.fd, "ready to write on bogus source"
        assert condition == gobject.IO_OUT, "ready to write on bogus condition"

        self.serial.write( self.datapending )
        self.datapending = ""
        self.watchReadyToSend = None
        return False

    def send( self, stream ):
        if not self.serial.isOpen():
            logger.warning( "Attempted to send something while serial is not open." )
            return
        self.datapending = self.datapending + stream
        if not self.watchReadyToSend:
            self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self.readyToSend )

#vim: expandtab
