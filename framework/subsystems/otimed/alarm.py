#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Time Daemon - Alarm Support

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: otimed
Module: alarm
"""

MODULE_NAME = "otimed.alarm"
__version__ = "0.1.3"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Time.Alarm"
DBUS_PATH_PREFIX = "/org/freesmartphone/Time/Alarm"

import dbus
import dbus.service

import gobject

import os, sys, time
from heapq import heappush, heappop, heapify

import logging
logger = logging.getLogger( MODULE_NAME )

import framework

def drop_dbus_result( *args ):
    if args:
        logger.warning( "unhandled dbus result: %s", args )

def log_dbus_error( desc ):
    def dbus_error( e, desc = desc ):
        logger.error( "%s (%s %s: %s)" % ( desc, e.__class__.__name__, e.get_dbus_name(), e.get_dbus_message() ) )
    return dbus_error


#----------------------------------------------------------------------------#
class Alarm( object ):
#----------------------------------------------------------------------------#
    """This class represents an alarm that has been set by an application

    Every application can have only one Alarm set. If the application has no
    well-known bus name, the Alarm will be cleared when then application
    disconnects from the bus.
    """
    def __init__( self, bus, busname, timestamp ):
        self.bus = bus
        self.busname = busname
        self.timestamp = timestamp

    def __cmp__( self, other ):
        return cmp( self.timestamp, other.timestamp )

    def _replyCallback( self ):
        pass

    def fire( self ):
        proxy = self.bus.get_object( self.busname, "/" )
        iface = dbus.Interface( proxy, "org.freesmartphone.Notification" )
        iface.Alarm(
            reply_handler=drop_dbus_result,
            error_handler=log_dbus_error( "error while calling Alarm on %s" % self.busname )
        )

#----------------------------------------------------------------------------#
class AlarmController( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Time.Alarm"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX

    def __init__( self, bus ):
        self.bus = bus
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX
        super(AlarmController, self).__init__(  bus, self.path )
        self.alarms = {}
        self.queue = []
        self.timer = None
        bus.add_signal_receiver(
            self._nameOwnerChangedHandler,
            "NameOwnerChanged",
            dbus.BUS_DAEMON_IFACE,
            dbus.BUS_DAEMON_NAME,
            dbus.BUS_DAEMON_PATH
        )

        # gather realtime clock dbus object
        o = bus.get_object( "org.freesmartphone.odeviced",
                            "/org/freesmartphone/Device/RealTimeClock/0",
                            follow_name_owner_changes=True,
                            introspect=False )
        self.rtc = dbus.Interface( o, "org.freesmartphone.RealTimeClock" )
        logger.info( "%s %s initialized. Serving %s at %s", self.__class__.__name__, __version__, self.interface, self.path )

    def _nameOwnerChangedHandler( self, name, old_owner, new_owner ):
        # TODO what happens when something changes it busname?
        if old_owner and not new_owner:
            if old_owner[0] == ':':
                self.ClearAlarm( old_owner, old_owner )

    def _verifyNameOwner( self, wellkown, connection ):
        if wellkown == connection:
            return True
        proxy = self.bus.get_object( dbus.BUS_DAEMON_NAME, dbus.BUS_DAEMON_PATH )
        iface = dbus.Interface( proxy, dbus.BUS_DAEMON_IFACE )
        return connection == iface.GetNameOwner( wellkown )

    def _schedule( self ):
        now = int(time.time())
        if not self.timer is None:
            gobject.source_remove( self.timer )
            self.timeout = None
        while self.queue and self.queue[0].timestamp <= now:
            alarm = heappop( self.queue )
            del self.alarms[ alarm.busname ]
            alarm.fire()
        if self.queue:
            self.timer = gobject.timeout_add_seconds( self.queue[0].timestamp - int(time.time()), self._schedule )
            self.rtc.SetWakeupTime(
                self.queue[0].timestamp,
                reply_handler=drop_dbus_result, error_handler=log_dbus_error( "RTC error; can not set wakeup time" )
            )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "si", "", sender_keyword='sender' ) # TODO maybe something bigger than int32
    def SetAlarm( self, busname, timestamp, sender ):
        if not busname:
            busname = sender
        if not busname[0] == ':' and not self._verifyNameOwner( busname, sender ):
            raise dbus.DBusException( "The bus name %s is not owned by %s" % (busname, sender) )
        old = self.alarms.get( busname, None )
        alarm = Alarm( self.bus, busname, timestamp )
        self.alarms[ busname ] = alarm
        if old is None:
            heappush(self.queue, alarm)
        else:
            self.queue[self.queue.index( old )] = alarm
            heapify( self.queue )
        self._schedule()

    @dbus.service.method( DBUS_INTERFACE, "s", "", sender_keyword='sender' )
    def ClearAlarm( self, busname, sender ):
        if not self._verifyNameOwner( busname, sender ):
            raise dbus.DBusException( "The bus name %s is not owned by %s" % (busname, sender) )
        old = self.alarms.pop( busname, None )
        if not old is None:
            self.queue.remove( old )
            heapify( self.queue )
        self._schedule()

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []
    objects.append( AlarmController( controller.bus ) )
    return objects

