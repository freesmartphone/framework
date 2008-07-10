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

DBUS_INTERFACE_PREFIX = "org.freedesktop.Gypsy"
DBUS_PATH_PREFIX = "/org/freedesktop/Gypsy"

import dbus
import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG
from gobject import idle_add

class GPSDevice( dbus.service.Object ):
    """An Dbus Object implementing org.freedesktop.Gypsy"""

    def __init__( self, bus ):
        self.interface = DBUS_INTERFACE_PREFIX
        self.path = DBUS_PATH_PREFIX
        self.bus = bus
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Accuracy", "", "iddd" )
    def GetAccuracy( self ):
        acc = self.gpsinfo.accuracy
        return acc.fields, acc.pdop, acc.hdop, acc.vdop

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Position", "", "iiddd" )
    def GetPosition( self ):
        pos = self.gpsinfo.position
        return pos.fields, pos.tstamp, pos.lat, pos.lon, pos.alt

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Accuracy", "iddd" )
    def AccuracyChanged( self, fields, pdop, hdop, vdop ):
        pass

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Position", "iiddd" )
    def PositionChanged( self, fields, tstamp, lat, lon, alt ):
        pass

#vim: expandtab
