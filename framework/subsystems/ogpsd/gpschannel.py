#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon - Parse NMEA/UBX data

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import os
import sys
import serial
import gobject

class GPSChannel( object ):
    """A GPS Channel :-)"""
    def __init__( self ):
        self.callback = None

    def setCallback( self, callback ):
        self.callback = callback

class SerialChannel( GPSChannel ):
    """Serial reader"""

    def __init__( self, path, baud = 2400):

        # set up serial port object and open it
        self.serial = serial.Serial()
        self.serial.port = path
        self.serial.baudrate = baud
        self.serial.rtscts = True
        self.serial.xonxoff = False
        self.serial.bytesize = serial.EIGHTBITS
        self.serial.parity = serial.PARITY_NONE
        self.serial.stopbits = serial.STOPBITS_ONE
        self.serial.timeout = None
        self.serial.open()

        assert self.serial.isOpen(), "Failure opening device"

        # set up I/O watches for mainloop
        self.watchReadyToRead = gobject.io_add_watch( self.serial.fd, gobject.IO_IN, self.readyToRead )
        #self.watchReadyToSend = gobject.io_add_watch( self.serial.fd, gobject.IO_OUT, self.readyToSend )
        # self.watchHUP = gobject.io_add_watch( self.serial.fd, gobject.IO_HUP, self.hup )

    def readyToRead( self, source, condition ):
        """Called, if data is available on the source."""
        assert source == self.serial.fd, "ready to read on bogus source"
        assert condition == gobject.IO_IN, "ready to read on bogus condition"

        try:
            inWaiting = self.serial.inWaiting()
        except IOError:
            inWaiting = 0

        data = self.serial.read( inWaiting )
        if self.callback:
            self.callback( data )

        return True

    def readyToSend( self, source, condition ):
        """Called, if source is ready to receive data."""
        assert source == self.serial.fd, "ready to write on bogus source"
        assert condition == gobject.IO_OUT, "ready to write on bogus condition"

        self.watchReadyToSend = None
        return False

#vim: expandtab
