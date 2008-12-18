#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
The Time Deamon - Python Implementation

(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: otimed
Module: otimed
"""

__version__ = "0.2.0"

from datetime import datetime, timedelta
from math import sqrt
import socket
import struct
import time

# All the dbus modules
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject

import logging
logger = logging.getLogger( 'otimed' )

def getOutput(cmd):
    from subprocess import Popen, PIPE
    return Popen(cmd, shell=True, stdout=PIPE).communicate()[0]

def toSeconds( delta ):
    return delta.days*24*60*60+delta.seconds+delta.microseconds*0.000001

#============================================================================#
class TimeSource( object ):
#============================================================================#
    def __init__( self, bus ):
        self.offset = None
        self.bus = bus

#============================================================================#
class GPSTimeSource( TimeSource ):
#============================================================================#
    def __init__( self, bus ):
        TimeSource.__init__( self, bus )
        self.invalidTimeout = None
        self.bus.add_signal_receiver(
            self._handleTimeChanged,
            "TimeChanged",
            "org.freedesktop.Gypsy.Time",
            None,
            None
        )

    def _handleTimeChanged( self, t ):
        if t:
            self.offset = datetime.utcfromtimestamp( t ) - datetime.utcnow()
            logger.debug( "GPS: offset=%f", toSeconds( self.offset ) )
        else:
            self.offset = None
            logger.debug( "GPS: time invalid", toSeconds( self.offset ) )
        if not self.invalidTimeout is None:
            gobject.source_remove( self.invalidTimeout )
            self.invalidTimeout = gobject.timeout_add_seconds( 300, self._handleInvaildTimeout )

    def _handleInvaildTimeout( self ):
        self.offset = None
        self.invalidTimeout = None
        logger.debug( "GPS: timeout" )
        return False

#============================================================================#
class NTPTimeSource( TimeSource ):
#============================================================================#
    def __init__( self, bus, server = "134.169.172.1", interval = 600 ):
        TimeSource.__init__( self, bus )
        self.server = server
        self.interval = interval
        self.socket = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        self.socket.bind( ('', 123) )
        self.socket.setblocking( False )
        self.updateTimeout = gobject.timeout_add_seconds( self.interval, self._handleUpdateTimeout )
        self.dataWatch = gobject.io_add_watch( self.socket.makefile(), gobject.IO_IN, self._handleData )
        self._handleUpdateTimeout()

    def _handleUpdateTimeout( self ):
        logger.debug( "NTP: requesting timestamp" )
        self.offset = None
        # FIXME do everything async
        data = '\x1b' + 47 * '\0'
        self.socket.sendto( data, ( self.server, 123 ))
        # reenable timeout
        return True

    def _handleData( self, source, condition ):
        epoch = 2208988800L
        data, address = self.socket.recvfrom( 1024 )
        if data:
            s, f = struct.unpack( '!12I', data )[10:12]
            s -= epoch
            t = s + f/(2.0**32)
            self.offset = datetime.utcfromtimestamp( t ) - datetime.utcnow()
            logger.debug( "NTP: offset=%f", toSeconds( self.offset ) )
        else:
            self.offset = None
            logger.warning( "NTP: no timestamp received" )

#============================================================================#
class Time( dbus.service.Object ):
#============================================================================#
    def __init__( self, bus ):
        self.path = "/org/freesmartphone/Time"
        super( Time, self ).__init__( bus, self.path )
        self.interface = "org.freesmartphone.Time"
        self.bus = bus

        self.sources = []
        self.sources.append( GPSTimeSource( self.bus ) )
        self.sources.append( NTPTimeSource( self.bus ) )

        self.interval = 90
        self.updateTimeout = gobject.timeout_add_seconds( self.interval, self._handleUpdateTimeout )

    def _handleUpdateTimeout( self ):
        logger.debug( "checking time sources" )
        offsets = []
        for source in self.sources:
            if not source.offset is None:
                offsets.append( toSeconds( source.offset ) )

        if not offsets:
            logger.debug( "no working time source" )
            return True

        n = len( offsets )
        mean = sum( offsets ) / n
        sd = sqrt( sum( (x-mean)**2 for x in offsets ) / n )
        logger.info( "offsets: n=%i mean=%f sd=%f", n, mean, sd )

        if sd < 15.0 < mean:
            logger.info( "adjusting clock by %f seconds" % mean )
            d = timedelta( seconds=mean )
            for source in self.sources:
                if not source.offset is None:
                    source.offset = source.offset - d
            t = datetime.utcnow() + d
            getOutput( "date -u -s %s" % t.strftime( "%m%d%H%M%Y.%S" ) )
            getOutput( "hwclock --systohc" )

        # reenable timeout
        return True

#============================================================================#
def factory( prefix, controller ):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    time_service = Time( controller.bus )
    return [time_service]

