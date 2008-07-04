#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon - UBX parser class

NMEA parser taken from pygps written by Russell Nelson
Copyright, 2001, 2002, Russell Nelson <pygps@russnelson.com>
Copyright permissions given by the GPL Version 2.  http://www.fsf.org/

(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2
"""

__version__ = "0.0.0"

import os
import sys
import math
import string
import struct
from gpsdevice import GPSDevice
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

class UBXDevice( GPSDevice ):
    def __init__( self, bus, gpschannel ):
        super( UBXDevice, self ).__init__( bus )

        self.buffer = ""
        self.gpschannel = gpschannel
        self.gpschannel.setCallback( self.parse )

        # TODO: Set device in UBX mode

    def parse( self, data ):
        self.buffer += data

        # Find the beginning of a UBX message
        start = self.buffer.find( chr( 0xb5 ) + chr( 0x62 ) )
        self.buffer = self.buffer[start:]
        # Minimum packet length is 8
        if len(self.buffer) < 8:
            return

        (cl, id, length) = struct.unpack("<xxBBH", self.buffer[:6])
        if len(self.buffer) < length + 8:
            return
        print "Got UBX packet %i, %i, %i" % (cl, id, length)
        self.buffer = self.buffer[length+8:]


    def checksum( self, msg ):
        ck_a = 0
        ck_b = 0
        for i in msg[2:]:
            ck_a = ck_a + ord(i)
            ck_b = ck_b + ck_a
        ck_a = ck_a % 255
        ck_b = ck_b % 255
        return (ck_a, ck_b)

#vim: expandtab
