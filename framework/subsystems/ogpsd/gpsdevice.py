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
        self.accuracy = ()
        self.position = ()

        self.interface = DBUS_INTERFACE_PREFIX
        self.path = DBUS_PATH_PREFIX
        self.bus = bus
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    def _updateAccuracy( self, fields, pdop, hdop, vdop ):
        if ( fields, pdop, hdop, vdop ) != self.accuracy:
            self.accuracy = ( fields, pdop, hdop, vdop )
            self.AccuracyChanged( *self.accuracy )

    def _updatePosition( self, fields, tstamp, lat, lon, alt ):
        if self.position == () or fields != self.position[0] or \
          lat != self.position[2] or lon != self.position[3] or \
          alt != self.position[4]:
            self.position = ( fields, tstamp, lat, lon, alt )
            self.PositionChanged( *self.position )
        else:
            # Update tstamp anyway
            self.position = ( fields, tstamp, lat, lon, alt )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Accuracy", "", "iddd" )
    def GetAccuracy( self ):
        return self.accuracy

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Position", "", "iiddd" )
    def GetPosition( self ):
        return self.position

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Accuracy", "iddd" )
    def AccuracyChanged( self, fields, pdop, hdop, vdop ):
        pass

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Position", "iiddd" )
    def PositionChanged( self, fields, tstamp, lat, lon, alt ):
        pass

#vim: expandtab
