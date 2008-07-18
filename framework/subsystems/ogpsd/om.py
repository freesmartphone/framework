#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

DBUS_INTERFACE = "org.freesmartphone.GPS"

import dbus
import dbus.service
import os
import sys
from ubx import UBXDevice
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG

class GTA02Device( UBXDevice ):
    """GTA02 specific GPS device"""

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "b", "" )
    def SetPower( self, power ):
        print "GPS Power set to", power
        proxy = self.bus.get_object( "org.freesmartphone.odeviced" , "/org/freesmartphone/Device/PowerControl/GPS" )
        gps = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        gps.SetPower( power, reply_handler=self._replyCallback, error_handler=self._errorCallback )

    def _replyCallback( self ):
        self.configure()

    def _errorCallback( self, e ):
        pass


#vim: expandtab
