#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2010 Denis 'GNUtoo' Carikli <GNUtoo@no-log.org>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Stefan Schmidt <stefan@datenfreihafen.org>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from nmea import NMEADevice

import helpers

import logging
logger = logging.getLogger('ogpsd')

class MSMDevice( NMEADevice ):
    """MSM SOC specific GPS device"""

    def __init__( self, bus, channel ):

        #TODO: stop "gps" from android-rpc if already launched

        NMEADevice.__init__( self, bus, channel )

    def initializeDevice( self ):
        #TODO: launch "gps" from android-rpc

        NMEADevice.initializeDevice( self )

    def shutdownDevice( self ):

        NMEADevice.shutdownDevice( self )

        #TODO: stop "gps" from android-rpc

#vim: expandtab
