#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

DEVICE_POWER_PATH = "/sys/devices/platform/s3c2440-i2c/i2c-adapter/i2c-0/0-0073/neo1973-pm-gps.0/pwron"

from ubx import UBXDevice
from ubx import CLIDPAIR

from framework.persist import persist

import helpers
import os
import sys
import marshal
import time

import logging
logger = logging.getLogger('ogpsd')

class GTA02Device( UBXDevice ):
    """GTA02 specific GPS device"""

    def __init__( self, bus, gpschannel ):
        self.power = False
        self.aidingData = persist.get( "ogpsd", "aidingdata" )
        if self.aidingData is None:
            self.aidingData = { "almanac": {}, "ephemeris": {}, "position": {} }

        super( GTA02Device, self ).__init__( bus, gpschannel )

    def initializeDevice( self ):
        helpers.writeToFile( DEVICE_POWER_PATH, "1" )

        # Reset the device
        #self.send("CFG-RST", 4, {"nav_bbr" : 0xffff, "Reset" : 0x01})

        super( GTA02Device, self ).initializeDevice()

        # Load aiding data and only if that succeeds have the GPS chip ask for it
        if self.aidingData["almanac"] or self.aidingData["ephemeris"] or self.aidingData["position"]:
            self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-REQ"][0] , "MsgID" : CLIDPAIR["AID-REQ"][1] , "Rate": 1 })

        # Enable NAV-POSECEF, AID-REQ (AID-DATA), AID-ALM, AID-EPH messages
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["NAV-POSECEF"][0] , "MsgID" : CLIDPAIR["NAV-POSECEF"][1] , "Rate": 8 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-ALM"][0] , "MsgID" : CLIDPAIR["AID-ALM"][1] , "Rate": 1 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-EPH"][0] , "MsgID" : CLIDPAIR["AID-EPH"][1] , "Rate": 1 })

    def shutdownDevice(self):
        # Save collected aiding data
        persist.set( "ogpsd", "aidingdata", self.aidingData )
        persist.sync( "ogpsd" )

        super( GTA02Device, self ).shutdownDevice()

        # Disable NAV-POSECEF, AID-REQ (AID-DATA), AID-ALM, AID-EPH messages
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["NAV-POSECEF"][0] , "MsgID" : CLIDPAIR["NAV-POSECEF"][1] , "Rate" : 0 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-REQ"][0] , "MsgID" : CLIDPAIR["AID-REQ"][1] , "Rate" : 0 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-ALM"][0] , "MsgID" : CLIDPAIR["AID-ALM"][1] , "Rate" : 0 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-EPH"][0] , "MsgID" : CLIDPAIR["AID-EPH"][1] , "Rate" : 0 })

        helpers.writeToFile( DEVICE_POWER_PATH, "0" )

    def handle_NAV_POSECEF( self, data ):
        data = data[0]
        if data["Pacc"] < 100000:
            self.aidingData["position"]["accuracy"] = data["Pacc"]
            self.aidingData["position"]["x"] = data["ECEF_X"]
            self.aidingData["position"]["y"] = data["ECEF_Y"]
            self.aidingData["position"]["z"] = data["ECEF_Z"]

    def handle_AID_DATA( self, data ):
        pos = self.aidingData["position"]

        # Position accuracy needs to rough, because device may have been moved
        pacc = 30000000 # in cm (300 KM)

        # GPS week number
        wn = int((time.time() - time.mktime(time.strptime("5 Jan 1980", "%d %b %Y"))) / (86400 * 7))

        # GPS time of week
        tow = int(time.time() - (time.mktime(time.strptime("5 Jan 1980", "%d %b %Y")) + wn * 86400 * 7)) * 1000

        # Time accuracy needs to be changed, because the RTC is imprecise
        tacc = 120000 # in ms (2 minutes)

        # Feed GPS with position and time
        if pos:
            self.send("AID-INI", 48, {"X" : pos["x"] , "Y" : pos["y"] , "Z" : pos["z"], "POSACC" : pacc, \
                      "TM_CFG" : 0 , "WN" : wn , "TOW" : tow , "TOW_NS" : 0 , "TACC_MS" : tacc , "TACC_NS" : 0 , \
                      "CLKD" : 0 , "CLKDACC" : 0 , "FLAGS" : 0x3 })

        # Feed gps with almanac
        if self.aidingData["almanac"]:
            for k, a in self.aidingData["almanac"].iteritems():
                logger.debug("Loaded almanac for SV %d" % a["SVID"])
                self.send("AID-ALM", 40, a);

        # Feed gps with ephemeris
        if self.aidingData["ephemeris"]:
            for k, a in self.aidingData["ephemeris"].iteritems():
                logger.debug("Loaded ephemeris for SV %d" % a["SVID"])
                self.send("AID-EPH", 104, a);

    def handle_AID_ALM( self, data ):
        data = data[0]
        # Save only, if there are values
        if "DWRD0" in data:
            self.aidingData["almanac"][ data["SVID"] ] = data

    def handle_AID_EPH( self, data ):
        data = data[0]
        # Save only, if there are values
        if "SF1D0" in data:
            self.aidingData["ephemeris"][ data["SVID"] ] = data

#vim: expandtab
