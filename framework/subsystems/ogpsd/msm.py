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
import os,subprocess

from nmea import NMEADevice

import helpers

import logging
logger = logging.getLogger('ogpsd')

class MSMDevice( NMEADevice ):
    """MSM SOC specific GPS device"""

    def __init__( self, bus, channel ):
        NMEADevice.__init__( self, bus, channel )
        self.dev_null = os.open("/dev/null",777)
        self.gps = None

    def initializeDevice( self ):
        NMEADevice.initializeDevice( self )
        if not self.gps:
            self.gps = subprocess.Popen(["gps"],stderr=self.dev_null,stdout=self.dev_null, shell=False)

    def shutdownDevice( self ):
	if self.gps:
            self.gps.kill()
            self.gps.wait()
            self.gps = None
        NMEADevice.shutdownDevice( self )

#vim: expandtab
