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

ID = {
    "ACK"  : 0x01,
    "NACK" : 0x00,
    "ALM"  : 0x30,
    "EPH"  : 0x31,
    "DATA" : 0x10,
    "HUI"  : 0x02,
    "INI"  : 0x01,
    "REQ"  : 0x00,
    "ANT"  : 0x13,
    "CFG"  : 0x09,
    "DAT"  : 0x06,
    "EKF"  : 0x12,
    "FXN"  : 0x0e,
    "INF"  : 0x02,
    "LIC"  : 0x80,
    "MSG"  : 0x01,
    "NAV2" : 0x1a,
    "NMEA" : 0x17,
    "PRT"  : 0x00,
    "RATE" : 0x08,
    "RST"  : 0x04,
    "RXM"  : 0x11,
    "SBAS" : 0x16,
    "TM"   : 0x10,
    "TM2"  : 0x19,
    "TMODE": 0x1d,
    "TP"   : 0x07,
    "USB"  : 0x1b,
    "DEBUG": 0x04,
    "ERROR": 0x00,
    "NOTICE" :0x02,
    "TEST" : 0x03,
    "USER" : 0x07,
    "WARNING" : 0x01,
    "EXCEPT" : 0x05,
    "HW"   : 0x09,
    "IO"   : 0x02,
    "IPC"  : 0x03,
    "MSGPP": 0x06,
    "RXBUF": 0x07,
    "SCHD" : 0x01,
    "TXBUF": 0x08,
    "USB"  : 0x0a,
    "VER"  : 0x04,
    "CLOCK": 0x22,
    "DGPS" : 0x31,
    "DOP"  : 0x04,
    "EKFSTATUS" : 0x40,
    "POSECEF" : 0x01,
    "POSLLH" : 0x02,
    "POSUTM" : 0x08,
    #"SBAS" : 0x32,
    "SOL" : 0x06,
    "STATUS" : 0x03,
    "SVINFO" : 0x30,
    "TIMEGPS" : 0x20,
    "TIMEUTC" : 0x21,
    "VELECEF" : 0x11,
    "VELNED" : 0x12,
    "POSREQ" : 0x40,
    "RAW"  : 0x10,
    "SFRB" : 0x11,
    "SVSI" : 0x20,
    "SVIN" : 0x04,
    "TM"   : 0x02,
    "TM2"  : 0x03,
    "TP"   : 0x01,
    "DOWNL": 0x01,
    "EXEC" : 0x03,
    "MEMCPY" : 0x04,
    "UPLOAD" : 0x02
}

MSGFMT = {
    ("NAV", "POSECEF", 20) :
        ["<IiiiI", ["ITOW", "ECEF_X", "ECEF_Y", "ECEF_Z", "Pacc"]],
#    ("NAV", "POSLLH", 28)
#    ("NAV", "POSUTM", 18)
    ("NAV", "DOP", 18) :
        ["<IHHHHHHH", ["ITOW", "GDOP", "PDOP", "TDOP", "VDOP", "HDOP", "NDOP", "EDOP"]],
    ("NAV", "STATUS", 16) :
        ["<IBBBBII", ["ITOW", "GPSfix", "Flags", "DiffS", "res", "TTFF", "MSSS"]],
    ("NAV", "SOL", 52) :
        ["<IihBBiiiIiiiIHBBI", ["ITOW", "Frac", "week", "GPSFix", "Flags", "ECEF_X", "ECEF_Y", "ECEF_Z", "Pacc",
         "ECEFVX", "ECEFVY", "ECEFVZ", "SAcc", "PDOP", "res1", "numSV", "res2"]],
#    ("NAV", "VELECEF", 20) :
#    ("NAV", "VELNED", 36) :
#    ("NAV", "TIMEGPS", 16) :
    ("NAV", "TIMEUTC", 20) :
        ["<IIiHBBBBBB", ["ITOW", "TAcc", "Nano", "Year", "Month", "Day", "Hour", "Min", "Sec", "Valid"]],
#    ("NAV", "CLOCK",  20) :
#    ("NAV", "SVINFO", 8+NCH*12) :
# NAV DGPS
# NAV SBAS
# NAV EKFSTATUS
# RXM
# INF
    ("ACK", "ACK", 2) :
        ["<BB", ["ClsID", "MsgID"]],
    ("ACK", "NACK", 2) :
        ["<BB", ["ClsID", "MsgID"]],
# CFG PRT
# CFG USB
    ("CFG", "MSG", 2) :
        ["<BB", ["Class", "MsgID"]],
    ("CFG", "MSG", 3) :
        ["<BBB", ["Class", "MsgID", "Rate"]],
# CFG NMEA
# CFG RATE
# CFG CFG
# CFG TP
    ("CFG", "NAV2", 40) :
        ["<BBHBBBBiBBBBBBHHHHHBBHII", ["Platform", "res0", "res1", "MinSVInitial", "MinSVs", "MaxSVs", "FixMode",
         "FixedAltitude", "MinCN0Initial", "MinCN0After", "MinELE", "DGPSTO", "MaxDR", "NAVOPT", "res2", "PDOP",
         "TDOP", "PACC", "TACC", "StaticThres", "res3", "res4", "res5", "res6"]],
# CFG DAT
# CFG INF
    ("CFG", "RST", 4) :
        ["<HBB", ["nav_bbr", "Reset", "Res"]],
    ("CFG", "RXM", 2) :
        ["<BB", ["gps_mode", "lp_mode"]],
# CFG ANT
    ("CFG", "FXN", 36) :
        ["<IIIIIIIII", ["flags", "t_reacq", "t_acq", "t_reacq_off", "t_acq_off", "t_on", "t_off", "res", "base_tow"]],
    ("CFG", "SBAS", 8) :
        ["<BBBBI", ["mode", "usage", "maxsbas", "reserved", "scanmode"]],
# CFG LIC
# CFG TM
# CFG TM2
# CFG TMODE
# CFG EKF
# UPD
# MON
    ("AID", "INI", 48) :
        ["<iiiIHHIiIIiII", ["X", "Y", "Z", "POSACC", "TM_CFG", "WM", "TOW", "TOW_NS", "TACC_MS", "TACC_NS", "CLKD", "CLKDACC", "FLAGS"]],
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
# TIM
}

MSGFMT_INV = dict( [ [(CLASS[cl], ID[id], le),v + [cl,id]] for (cl,id,le),v in MSGFMT.items() ] )

class UBXDevice( GPSDevice ):
    def __init__( self, bus, gpschannel ):
        super( UBXDevice, self ).__init__( bus )

        self.buffer = ""
        self.gpschannel = gpschannel
        self.gpschannel.setCallback( self.parse )

        # TODO: Set device in UBX mode
#        self.send("CFG", "SBAS", 8, {"mode" : 3, "usage" : 7, "maxsbas" : 2, "reserved" : 0, "scanmode" : 0})

    def parse( self, data ):
        self.buffer += data
        while True:
            # Find the beginning of a UBX message
            start = self.buffer.find( chr( SYNC1 ) + chr( SYNC2 ) )
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

    def send( self, cl, id, length, payload ):
        format = MSGFMT[(cl,id,length)]
        stream = struct.pack("<BBBBH", SYNC1, SYNC2, CLASS[cl], ID[id], length)
        stream = stream + struct.pack(format[0], *[payload[i] for i in format[1]])
        stream = stream + struct.pack("<BB", *self.checksum( stream[2:] ))
        self.gpschannel.send( stream )

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
            format = MSGFMT_INV[(cl, id, length)]
        except KeyError:
            print "Unknown message", cl, id, length
            return

        payload = zip(format[1], struct.unpack(format[0], payload))
        print format[2], format[3], payload


#vim: expandtab
