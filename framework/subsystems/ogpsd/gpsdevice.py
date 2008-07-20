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
        self.gpsfixstatus = 0
        self.fixstatus = 0
        self.position = ()
        self.accuracy = ()
        self.course = ()
        self.satellites = []

        self.interface = DBUS_INTERFACE_PREFIX
        self.path = DBUS_PATH_PREFIX
        self.bus = bus
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    def _updateFixStatus( self, fixstatus ):
        if self.fixstatus != fixstatus:
            self.fixstatus = fixstatus
            self.FixStatusChanged( self.fixstatus )

    def _updatePosition( self, fields, tstamp, lat, lon, alt ):
        if self.position == () or fields != self.position[0] or \
          lat != self.position[2] or lon != self.position[3] or \
          alt != self.position[4]:
            self.position = ( fields, tstamp, lat, lon, alt )
            self.PositionChanged( *self.position )
        else:
            # Update tstamp anyway
            self.position = ( fields, tstamp, lat, lon, alt )

    def _updateAccuracy( self, fields, pdop, hdop, vdop ):
        if ( fields, pdop, hdop, vdop ) != self.accuracy:
            self.accuracy = ( fields, pdop, hdop, vdop )
            self.AccuracyChanged( *self.accuracy )

    def _updateCourse( self, fields, tstamp, speed, heading, climb ):
        if self.course == () or self.course[2:] != ( speed, heading, climb ):
            self.course = ( fields, tstamp, speed, heading, climb )
            self.CourseChanged( *self.course )
        else:
            # Update tstamp so a GetCourse returns the current one
            self.course = ( fields, tstamp, speed, heading, climb )

    def _updateSatellites( self, satellites ):
        # Is this check sufficient or could some SVs switch channels, but
        # otherwise stay identical?
        if self.satellites != satellites:
            self.satellites = satellites
            self.SatellitesChanged( self.satellites )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Device", "", "i")
    def GetFixStatus( self ):
        return self.fixstatus

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Position", "", "iiddd" )
    def GetPosition( self ):
        return self.position

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Accuracy", "", "iddd" )
    def GetAccuracy( self ):
        return self.accuracy

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Course", "", "iiddd" )
    def GetCourse( self ):
        return self.course

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Satellite", "", "a(ubuuu)" )
    def GetSatellites( self ):
        return self.satellites


    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Device", "i" )
    def FixStatusChanged( self, fixstatus ):
        pass

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Position", "iiddd" )
    def PositionChanged( self, fields, tstamp, lat, lon, alt ):
        pass

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Accuracy", "iddd" )
    def AccuracyChanged( self, fields, pdop, hdop, vdop ):
        pass

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Course", "iiddd" )
    def CourseChanged( self, fields, tstamp, speed, heading, climb ):
        pass

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Satellite", "a(ubuuu)" )
    def SatellitesChanged( self, satellites ):
        pass

#vim: expandtab
