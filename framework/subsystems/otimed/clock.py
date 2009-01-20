# -*- coding: UTF-8 -*-
"""
Open Time Daemon - Kernel clock interface

(C) 2009 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2009 Openmoko, Inc.
GPLv2 or later

Package: otimed
Module: clock
"""

from ctypes import *
from ctypes.util import find_library
import math

ADJ_OFFSET = 0x0001

class TIMEVAL(Structure):
    _fields_ = [
        ("sec", c_long),
        ("usec", c_long),
     ]

class TIMEX(Structure):
    _fields_ = [
        ("modes", c_int),
        ("offset", c_long),
        ("freq", c_long),
        ("maxerror", c_long),
        ("esterror", c_long),
        ("status", c_int),
        ("constant", c_long),
        ("precision", c_long),
        ("tolerance", c_long),
        ("time", TIMEVAL),
        ("tick", c_long),

        ("ppsfreq", c_long),
        ("jitter", c_long),
        ("shift", c_int),
        ("stabil", c_long),
        ("jitcnt", c_long),
        ("calcnt", c_long),
        ("errcnt", c_long),
        ("stbcnt", c_long),

        ("reserved", c_int32 * 12),
    ]

libc = CDLL(find_library("c"))

def adjust(delta):
    tx = TIMEX()
    print libc.adjtimex(byref(tx))
    dsec = int(math.floor(delta))
    dusec = int( (delta - dsec) * 1000000 )
    usec = tx.time.usec + dusec
    overflow, usec = divmod( usec, 1000000 )
    sec = tx.time.sec + dsec + overflow
    tv = TIMEVAL(sec, usec)
    print libc.settimeofday(byref(tv), None)

