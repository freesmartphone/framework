# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: fso_triggers
"""

from trigger import DBusTrigger

import dbus

import logging
logger = logging.getLogger('oeventsd')

#============================================================================#
class CallStatusTrigger(DBusTrigger):
#============================================================================#
    """Just a sugar trigger for a GSM call status change"""

    function_name = 'CallStatus'

    def __init__(self):
        bus = dbus.SystemBus()
        super(CallStatusTrigger, self).__init__(
            bus,
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/Device',
            'org.freesmartphone.GSM.Call',
            'CallStatus'
        )
    def on_signal(self, id, status, properties):
        logger.info("Receive CallStatus, status = %s", status)
        self(id=id, status=status, properties=properties)

    def __repr__(self):
        return "CallStatus"

#============================================================================#
class PowerStatusTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Device.PowerSupply.PowerStatus
    """

    function_name = 'PowerStatus'

    def __init__(self):
        bus = dbus.SystemBus()
        super(PowerStatusTrigger, self).__init__(
            bus,
            'org.freesmartphone.odeviced',
            None,
            'org.freesmartphone.Device.PowerSupply',
            'PowerStatus'
        )
    def on_signal(self, status):
        logger.info("Receive PowerStatus, status = %s", status)
        self(status=status)

    def __repr__(self):
        return "PowerStatus"

#============================================================================#
class TimeTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Time.Minute
    """

    function_name = 'Time'

    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        bus = dbus.SystemBus()
        super(TimeTrigger, self).__init__(
            bus,
            'org.freesmartphone.otimed',
            '/org/freesmartphone/Time',
            'org.freesmartphone.Time',
            'Minute'
        )
    def on_signal(self, year, mon, day, hour, min, sec, wday, yday, isdst):
        if self.hour == hour and self.minute == min:
            logger.debug("%s triggered", self)
            self()

    def __repr__(self):
        return "Time(%d:%d)" % (self.hour, self.minute)

