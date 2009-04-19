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

__version__ = "0.2.2"
MODULE_NAME = "otimed"

import clock

from framework.config import config

from datetime import datetime, timedelta
from math import sqrt
import shutil
import socket
import struct
import time

# All the dbus modules
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

def getOutput(cmd):
    from subprocess import Popen, PIPE
    return Popen(cmd, shell=True, stdout=PIPE).communicate()[0]

def toSeconds( delta ):
    return delta.days*24*60*60+delta.seconds+delta.microseconds*0.000001

def drop_dbus_result( *args ):
    if args:
        logger.warning( "unhandled dbus result: %s", args )

def log_dbus_error( desc ):
    def dbus_error( e, desc = desc ):
        logger.error( "%s (%s %s: %s)" % ( desc, e.__class__.__name__, e.get_dbus_name(), e.get_dbus_message() ) )
    return dbus_error

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
            logger.debug( "GPS: time invalid" )
        if not self.invalidTimeout is None:
            gobject.source_remove( self.invalidTimeout )
            self.invalidTimeout = gobject.timeout_add_seconds( 300, self._handleInvaildTimeout )

    def _handleInvaildTimeout( self ):
        self.offset = None
        self.invalidTimeout = None
        logger.debug( "GPS: timeout" )
        return False

    def __repr__( self ):
        return "<%s>" % ( self.__class__.__name__, )

#============================================================================#
class NTPTimeSource( TimeSource ):
#============================================================================#
    def __init__( self, bus, server, interval = 600 ):
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
        try:
            self.socket.sendto( data, ( self.server, 123 ))
        except:
            logger.debug( "NTP: failed to request timestamp" )
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

    def __repr__( self ):
        return "<%s checking %s every %s seconds>" % ( self.__class__.__name__, self.server, self.interval )

#============================================================================#
class GSMZoneSource( object ):
#============================================================================#
    def __init__( self, bus ):
        self.zone = None
        self.mccmnc = None
        self.isocode = None
        self.bus = bus
        self.bus.add_signal_receiver(
            self._handleNetworkStatusChanged,
            "Status",
            "org.freesmartphone.GSM.Network",
            None,
            None
        )
        self.bus.add_signal_receiver(
            self._handleTimeZoneReport,
            "TimeZoneReport",
            "org.freesmartphone.GSM.Network",
            None,
            None
        )
        proxy = bus.get_object( "org.freesmartphone.ogsmd",
                                "/org/freesmartphone/GSM/Server",
                                follow_name_owner_changes=True,
                                introspect=False )
        self.gsmdata = dbus.Interface( proxy, "org.freesmartphone.GSM.Data",  )

    def _handleTimeZoneReport( self, report ):
	# this can be improved - AA
	# if we know the country, the offset and if this zone supports daylight savings
	# the proper timezone can be derived.
	# so opreferencesd needs to have a <this zone uses daylight savings> flag
	# and we need a /usr/share/zoneinfo parser

	# CTZV is offset * 4
	offset = report / 4
	# offset need to be inverted to get the correct TZ
	zone = "Etc/GMT"
	if offset <= 0 :
		zone += "+" + str( offset * -1 )
	else :
		zone += "-" + str( offset )
	logger.debug( "TimeZoneReport :" + str( report ) + " offset " + str( offset ) + " zone " + zone )
	if zone != self.zone :
            try:
                shutil.copyfile( "/usr/share/zoneinfo/"+zone, "/etc/localtime" )
		self.zone = zone
            except:
                logger.warning( "failed to install time zone file " + zone + " to /etc/localtime" )

    def _handleNetworkStatusChanged( self, status ):
        if "code" in status:
            code = status["code"]
            if self.mccmnc == code:
                return
            self.mccmnc = code
            mcc = code[:3]
            mnc = code[3:]
            logger.debug( "GSM: MCC=%s MNC=%s", mcc, mnc )
            self.gsmdata.GetNetworkInfo(
                mcc, mnc,
                reply_handler=self._handleNetworkInfoReply,
                error_handler=log_dbus_error( "error while calling org.freesmartphone.GSM.Data.GetNetworkInfo" )
            )
        else:
            self.zone = None
            logger.debug( "GSM: no network code" )

    def _handleNetworkInfoReply( self, info ):
        if "iso" in info:
            if self.isocode == info["iso"]:
                return
            self.isocode = info["iso"]
            logger.debug( "GSM: ISO-Code %s", info["iso"] )
            for line in open( "/usr/share/zoneinfo/zone.tab", "r" ):
                data = line.rstrip().split( "\t" )
                if self.isocode == data[0]:
                    self.zone = data[2]
                    break
            logger.info( "GSM: Zone %s", self.zone )
            try:
                shutil.copyfile( "/usr/share/zoneinfo/"+self.zone, "/etc/localtime" )
            except:
                logger.warning( "failed to install time zone file to /etc/localtime" )
        else:
            self.zone = None
            logger.debug( "GSM: no ISO-Code for this network" )

    def __repr__( self ):
        return "<%s>" % ( self.__class__.__name__, )

#============================================================================#
class Time( dbus.service.Object ):
#============================================================================#
    def __init__( self, bus ):
        self.path = "/org/freesmartphone/Time"
        super( Time, self ).__init__( bus, self.path )
        self.interface = "org.freesmartphone.Time"
        self.bus = bus

        timesources = [x.strip().upper() for x in config.getValue( "otimed", "timesources", "GPS,NTP").split( ',' )]
        zonesources = [x.strip().upper() for x in config.getValue( "otimed", "zonesources", "GSM").split( ',' )]
        ntpserver = config.getValue( "otimed", "ntpserver", "134.169.172.1").strip()

        self.timesources = []
        if 'GPS' in timesources:
            self.timesources.append( GPSTimeSource( self.bus ) )
        if 'NTP' in timesources:
            self.timesources.append( NTPTimeSource( self.bus, ntpserver ) )

        logger.info( "loaded timesources %s", self.timesources )

        self.zonesources = []
        if 'GSM' in zonesources:
            self.zonesources.append( GSMZoneSource( self.bus ) )

        logger.info( "loaded zonesources %s", self.zonesources )

        self.interval = 90
        self.updateTimeout = gobject.timeout_add_seconds( self.interval, self._handleUpdateTimeout )

    def _handleUpdateTimeout( self ):
        logger.debug( "checking time sources" )
        offsets = []
        for source in self.timesources:
            if not source.offset is None:
                offsets.append( toSeconds( source.offset ) )

        if not offsets:
            logger.debug( "no working time source" )
            return True

        n = len( offsets )
        mean = sum( offsets ) / n
        sd = sqrt( sum( (x-mean)**2 for x in offsets ) / n )
        logger.info( "offsets: n=%i mean=%f sd=%f", n, mean, sd )

        if sd < 15.0 < abs( mean ):
            logger.info( "adjusting clock by %f seconds" % mean )
            d = timedelta( seconds=mean )
            for source in self.timesources:
                if not source.offset is None:
                    source.offset = source.offset - d
            clock.adjust( mean )
            getOutput( "hwclock --systohc --utc" )

        # reenable timeout
        return True

#============================================================================#
def factory( prefix, controller ):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    time_service = Time( controller.bus )
    return [time_service]

