#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon - Parse NMEA/UBX data

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

DBUS_INTERFACE_PREFIX = "org.freedesktop.Gypsy"
DBUS_PATH_PREFIX = "/org/freedesktop/Gypsy"

from framework import resource
import framework.patterns.tasklet as tasklet
import dbus
import dbus.service

import logging
logger = logging.getLogger('ogpsd')

class GPSDevice( resource.Resource ):
    """An Dbus Object implementing org.freedesktop.Gypsy"""
    enabled = False

    def __init__( self, bus, channel=None ):
        self._fixstatus = 0
        self._position = [ 0, 0, 0.0, 0.0, 0.0 ]
        self._accuracy = [ 0, 0.0, 0.0, 0.0 ]
        self._course = [ 0, 0, 0.0, 0.0, 0.0 ]
        self._satellites = []
        self._time = 0
        self._users = []

        self.channel = channel
        self.interface = DBUS_INTERFACE_PREFIX
        self.path = DBUS_PATH_PREFIX
        self.bus = bus
        self.usageiface = None
        bus.add_signal_receiver(
            self.nameOwnerChangedHandler,
            "NameOwnerChanged",
            dbus.BUS_DAEMON_IFACE,
            dbus.BUS_DAEMON_NAME,
            dbus.BUS_DAEMON_PATH
        )

        super( GPSDevice, self ).__init__( bus, self.path, name='GPS' )
        logger.info("%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    def nameOwnerChangedHandler( self, name, old_owner, new_owner ):
        if old_owner and not new_owner:
            if old_owner in self._users:
                self.Stop( old_owner, lambda :None, lambda x:None)


    #
    # framework.Resource
    #
    def _enable( self, on_ok, on_error ):
        logger.info( "enabling" )
	enabled = True
        self.channel.initializeChannel()
        self.initializeDevice()
        self.ConnectionStatusChanged( True )
        on_ok()

    def _disable( self, on_ok, on_error ):
	enabled = False
        logger.info( "disabling" )
        self.ConnectionStatusChanged( False )
        self.shutdownDevice()
        self.channel.shutdownChannel()
        on_ok()

    def _suspend( self, on_ok, on_error ):
	if enabled:
            logger.info( "suspending" )
            self.ConnectionStatusChanged( False )
            self.suspendDevice()
            self.channel.suspendChannel()
            on_ok()

    def _resume( self, on_ok, on_error ):
	if enabled:
	    logger.info("resuming")
            self.channel.resumeChannel()
            self.resumeDevice()
            self.ConnectionStatusChanged( True )
            on_ok()

    def initializeDevice( self ):
        pass

    def shutdownDevice( self ):
        self._reset()

    def suspendDevice( self ):
        self.shutdownDevice()

    def resumeDevice( self ):
        self.initializeDevice()

    def _reset( self ):
        if self._fixstatus:
            self._fixstatus = 0
            self.FixStatusChanged( self._fixstatus )
        if self._position[0]:
            self._position[0] = 0
            self.PositionChanged( *self._position )
        if self._accuracy[0]:
            self._accuracy[0] = 0
            self.AccuracyChanged( *self._accuracy )
        if self._course[0]:
            self._course[0] = 0
            self.CourseChanged( *self._course )
        if self._satellites != []:
            self._satellites = []
            self.SatellitesChanged( self._satellites )
        if self._time:
            self._time = 0
            self.TimeChanged( self._time )

    #
    # update functions
    #
    def _updateFixStatus( self, fixstatus ):
        if self._fixstatus != fixstatus:
            self._fixstatus = fixstatus
            self.FixStatusChanged( self._fixstatus )

    def _updatePosition( self, fields, lat, lon, alt ):
        changed = False
        if self._position[0] != fields:
            self._position[0] = fields
            changed = True
        if fields:
            self._position[1] = self._time
        if fields & (1 << 0) and self._position[2] != lat:
            self._position[2] = lat
            changed = True
        if fields & (1 << 1) and self._position[3] != lon:
            self._position[3] = lon
            changed = True
        if fields & (1 << 2) and self._position[4] != alt:
            self._position[4] = alt
            changed = True
        if changed:
            self.PositionChanged( *self._position )

    def _updateAccuracy( self, fields, pdop, hdop, vdop ):
        changed = False
        if self._accuracy[0] != fields:
            self._accuracy[0] = fields
            changed = True
        if fields & (1 << 0) and self._accuracy[1] != pdop:
            self._accuracy[1] = pdop
            changed = True
        if fields & (1 << 1) and self._accuracy[2] != hdop:
            self._accuracy[2] = hdop
            changed = True
        if fields & (1 << 2) and self._accuracy[3] != vdop:
            self._accuracy[3] = vdop
            changed = True
        if changed:
            self.AccuracyChanged( *self._accuracy )

    def _updateCourse( self, fields, speed, heading, climb ):
        changed = False
        if self._course[0] != fields:
            self._course[0] = fields
            changed = True
        if fields:
            self._course[1] = self._time
        if fields & (1 << 0) and self._course[2] != speed:
            self._course[2] = speed
            changed = True
        if fields & (1 << 1) and self._course[3] != heading:
            self._course[3] = heading
            changed = True
        if fields & (1 << 2) and self._course[4] != climb:
            self._course[4] = climb
            changed = True
        if changed:
            self.CourseChanged( *self._course )

    def _updateSatellites( self, satellites ):
        # Is this check sufficient or could some SVs switch channels, but
        # otherwise stay identical?
        if self._satellites != satellites:
            self._satellites = satellites
            self.SatellitesChanged( self._satellites )

    def _updateTime( self, time ):
        if self._time != time:
            self._time = time
            self.TimeChanged( self._time )

    # Gypsy Server interface
    # This should be implemented somewhere else once we allow different devices
    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Server", "s", "o" )
    def Create( self, device ):
        return DBUS_PATH_PREFIX

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Server", "o", "" )
    def Shutdown( self, path ):
        pass

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Device", "", "", sender_keyword="sender", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Start( self, sender, dbus_ok, dbus_error ):
        if not sender in self._users:
            self._users.append( sender )
            if len(self._users) == 1:
                if not self.usageiface:
                    usage = self.bus.get_object( "org.freesmartphone.ousaged", "/org/freesmartphone/Usage", follow_name_owner_changes=True )
                    self.usageiface = dbus.Interface( usage, "org.freesmartphone.Usage" )
                self.usageiface.RequestResource("GPS", reply_handler=dbus_ok, error_handler=dbus_error )
            else:
                dbus_ok()
        else:
            dbus_ok()

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Device", "", "", sender_keyword="sender", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Stop( self, sender, dbus_ok, dbus_error ):
        if sender in self._users:
            self._users.remove( sender )
            if self._users == []:
                if not self.usageiface:
                    usage = self.bus.get_object( "org.freesmartphone.ousaged", "/org/freesmartphone/Usage", follow_name_owner_changes=True )
                    self.usageiface = dbus.Interface( usage, "org.freesmartphone.Usage" )
                self.usageiface.ReleaseResource("GPS", reply_handler=dbus_ok, error_handler=dbus_error )
            else:
                dbus_ok()
        else:
            dbus_ok()

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Device", "", "b")
    @resource.checkedsyncmethod
    def GetConnectionStatus( self ):
        return self._resourceStatus == "enabled"

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Device", "", "i")
    @resource.checkedsyncmethod
    def GetFixStatus( self ):
        return self._fixstatus

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Position", "", "iiddd" )
    @resource.checkedsyncmethod
    def GetPosition( self ):
        return self._position

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Accuracy", "", "iddd" )
    @resource.checkedsyncmethod
    def GetAccuracy( self ):
        return self._accuracy

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Course", "", "iiddd" )
    @resource.checkedsyncmethod
    def GetCourse( self ):
        return self._course

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Satellite", "", "a(ubuuu)" )
    @resource.checkedsyncmethod
    def GetSatellites( self ):
        return self._satellites

    @dbus.service.method( DBUS_INTERFACE_PREFIX + ".Time", "", "i" )
    @resource.checkedsyncmethod
    def GetTime( self ):
        return self._time


    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Device", "b" )
    def ConnectionStatusChanged( self, constatus ):
        pass

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

    @dbus.service.signal( DBUS_INTERFACE_PREFIX + ".Time", "i" )
    def TimeChanged( self, time ):
        pass


class DummyDevice( GPSDevice ):
    """A dummy device that reports a static position"""
    def __init__( self, bus, channel ):
        super( DummyDevice, self ).__init__( bus )

    def initializeDevice( self ):
        self._updateTime( 1 )
        self._updateFixStatus( 3 )
        self._updatePosition( 7, 23.54322, -42.65648, 14.4 )
        self._updateAccuracy( 7, 2.34, 16.4, 1.4 )
        self._updateCourse( 7, 240.4, 45.4, -4.4 )
        self._updateSatellites( [(1, False, 13, 164, 0), (13, True, 72, 250, 20), (24, True, 68, 349, 31)] )

#vim: expandtab
