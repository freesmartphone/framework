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
from helpers import LOG
from gobject import idle_add

SYNC1=0xb5
SYNC2=0x62

CLASS = {
    "NAV" : 0x01,
    "RXM" : 0x02,
    "INF" : 0x04,
    "ACK" : 0x05,
    "CFG" : 0x06,
    "UPD" : 0x09,
    "MON" : 0x0a,
    "AID" : 0x0b,
    "TIM" : 0x0d,
    "USR" : 0x40
}

CLASS_INV = dict( [ [v,k] for k,v in CLASS.items() ] )

ID = {
    "ACK"  : 0x01,
    "NACK" : 0x00,
    "ALM"  : 0x30,
    "DATA" : 0x10,
    "EPH"  : 0x31,
    "HUI"  : 0x02,
    "INI"  : 0x01,
    "REQ"  : 0x00,
    "ANT"  : 0x13,
    "CFG"  : 0x09
}

ID_INV = dict( [ [v,k] for k,v in ID.items() ] )

UBX_MSGFMT = {
    ("AID", "HUI", 72) :
        ["<IddNHHHHHHffffffffI", ["HEALTH", "UTC_A1", "UTC_A0", "UTC_TOT", "UTC_WNT",
         "UTC_LS", "UTC_WNF", "UTC_DN", "UTC_LSF", "UTC_SPARE", "KLOB_A0", "KLOB_A1",
         "KLOB_A2", "KLOB_A3", "KLOB_B0", "KLOB_B1", "KLOB_B2", "KLOB_B3", "FLAGS"]],
    ("AID", "ALM", 1) :
        ["<B", ["SVID"]],
    ("AID", "ALM", 8)  :
        ["<II", ["SVID", "WEEK"]],
    ("AID", "ALM", 40) :
        ["<" + "I"*10, ["SVID", "WEEK", "DWRD0", "DWRD1", "DWRD2", "DWRD3", "DWRD4", "DWRD5", "DWRD6", "DWRD7"]],
    ("AID", "EPH", 1) :
        ["<B", ["SVID"]],
    ("AID", "EPH", 8) :
        ["<II", ["SVID", "HOW"]],
    ("AID", "EPH", 104) :
        ["<" + "I"*26, ["SVID", "HOW", "SF1D0", "SF1D1", "SF1D2", "SF1D3", "SF1D4",
            "SF1D5", "SF1D6", "SF1D7", "SF2D0", "SF2D1", "SF2D2", "SF2D3", "SF2D4",
            "SF2D5", "SF2D6", "SF1D7", "SF3D0", "SF3D1", "SF3D2", "SF3D3", "SF3D4", "SF3D5", "SF3D6", "SF3D7"]]
}

class UBXDevice( GPSDevice ):
    def __init__( self, bus, gpschannel ):
        super( UBXDevice, self ).__init__( bus )

        self.buffer = ""
        self.gpschannel = gpschannel
        self.gpschannel.setCallback( self.parse )

        # TODO: Set device in UBX mode

    def parse( self, data ):
        self.buffer += data

        while True:
            # Find the beginning of a UBX message
            start = self.buffer.find( chr( 0xb5 ) + chr( 0x62 ) )
            self.buffer = self.buffer[start:]
            # Minimum packet length is 8
            if len(self.buffer) < 8:
                return

            (cl, id, length) = struct.unpack("<xxBBH", self.buffer[:6])
            if len(self.buffer) < length + 8:
                return

            if self.checksum(self.buffer[2:length+6]) != struct.unpack("<BB", self.buffer[length+6:length+8]):
                self.buffer = self.buffer[2:]
                continue

            # Now we got a valid UBX packet, decode it
            self.decode(cl, id, length, self.buffer[6:length+6])

            # Discard packet
            self.buffer = self.buffer[length+8:]

    def checksum( self, msg ):
        ck_a = 0
        ck_b = 0
        for i in msg:
            ck_a = ck_a + ord(i)
            ck_b = ck_b + ck_a
        ck_a = ck_a % 256
        ck_b = ck_b % 256
        return (ck_a, ck_b)

    def decode( self, cl, id, length, payload ):
        try:
            format = UBX_MSGFMT[(CLASS_INV[cl], ID_INV[id], length)]
        except KeyError:
            print "Unknown message", CLASS_INV[cl], ID_INV[id], length
            return

        payload = zip(format[1], struct.unpack(format[0], payload))
        print payload


#vim: expandtab
