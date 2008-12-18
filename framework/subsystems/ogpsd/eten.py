#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Stefan Schmidt <stefan@datenfreihafen.org>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

DEVICE_POWER_PATH = "/sys/bus/platform/devices/neo1973-pm-gps.0/pwron"

from nmea import NMEADevice

import helpers

import logging
logger = logging.getLogger('ogpsd')

class EtenDevice( NMEADevice ):
    """E-Ten specific GPS device"""

    def __init__( self, bus, channel ):

        # Make sure the GPS is off
        helpers.writeToFile( DEVICE_POWER_PATH, "0" )

        NMEADevice.__init__( self, bus, channel )

    def initializeDevice( self ):
        helpers.writeToFile( DEVICE_POWER_PATH, "1" )

        NMEADevice.initializeDevice( self )

    def shutdownDevice( self ):

        NMEADevice.shutdownDevice( self )

        helpers.writeToFile( DEVICE_POWER_PATH, "0" )

#vim: expandtab
