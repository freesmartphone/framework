#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.9.1"
MODULE_NAME = "ogpsd"

DEVICE_POWER_PATH = "/sys/bus/platform/devices/neo1973-pm-gps.0/pwron"

from ubx import UBXDevice
from ubx import CLIDPAIR

from framework.persist import persist
import helpers

import gobject
import os, sys, marshal, time
from datetime import datetime, timedelta

import logging
logger = logging.getLogger( MODULE_NAME )

class GTA02Device( UBXDevice ):
    """GTA02 specific GPS device"""

    def __init__( self, bus, channel ):

        # Make sure the GPS is off
        helpers.writeToFile( DEVICE_POWER_PATH, "0" )

        self.aidingData = persist.get( "ogpsd", "aidingdata" )
        if self.aidingData is None:
            self.aidingData = { "almanac": {}, "ephemeris": {}, "position": {}, "hui": {} }

        super( GTA02Device, self ).__init__( bus, channel )

    def initializeDevice( self ):
        helpers.writeToFile( DEVICE_POWER_PATH, "1" )

        # Wait for the device to be powered up
        time.sleep(0.5)

        # Reset the device
        #self.send("CFG-RST", 4, {"nav_bbr" : 0xffff, "Reset" : 0x01})

        super( GTA02Device, self ).initializeDevice()

        # Load aiding data and only if that succeeds have the GPS chip ask for it
        if self.aidingData["almanac"] or self.aidingData["ephemeris"] or self.aidingData["position"]:
            self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-REQ"][0] , "MsgID" : CLIDPAIR["AID-REQ"][1] , "Rate": 1 })

        # Enable NAV-POSECEF, AID-REQ (AID-DATA), AID-ALM, AID-EPH messages
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["NAV-POSECEF"][0] , "MsgID" : CLIDPAIR["NAV-POSECEF"][1] , "Rate": 8 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-ALM"][0] , "MsgID" : CLIDPAIR["AID-ALM"][1] , "Rate": 1 })
        #self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-EPH"][0] , "MsgID" : CLIDPAIR["AID-EPH"][1] , "Rate": 1 })
        self.huiTimeout = gobject.timeout_add_seconds( 300, self.requestHuiTimer )

    def shutdownDevice(self):
        # Disable NAV-POSECEF, AID-REQ (AID-DATA), AID-ALM, AID-EPH messages
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["NAV-POSECEF"][0] , "MsgID" : CLIDPAIR["NAV-POSECEF"][1] , "Rate" : 0 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-REQ"][0] , "MsgID" : CLIDPAIR["AID-REQ"][1] , "Rate" : 0 })
        self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-ALM"][0] , "MsgID" : CLIDPAIR["AID-ALM"][1] , "Rate" : 0 })
        #self.send("CFG-MSG", 3, {"Class" : CLIDPAIR["AID-EPH"][0] , "MsgID" : CLIDPAIR["AID-EPH"][1] , "Rate" : 0 })
        if self.huiTimeout:
            gobject.source_remove( self.huiTimeout )
            self.huiTimeout = None

        super( GTA02Device, self ).shutdownDevice()

        helpers.writeToFile( DEVICE_POWER_PATH, "0" )

        # Save collected aiding data
        persist.set( "ogpsd", "aidingdata", self.aidingData )
        persist.sync( "ogpsd" )

    def handle_NAV_POSECEF( self, data ):
        data = data[0]
        if data["Pacc"] < 100000:
            self.aidingData["position"]["accuracy"] = data["Pacc"]
            self.aidingData["position"]["x"] = data["ECEF_X"]
            self.aidingData["position"]["y"] = data["ECEF_Y"]
            self.aidingData["position"]["z"] = data["ECEF_Z"]

    def handle_AID_DATA( self, data ):
        pos = self.aidingData.get("position", None)

        # Let's just try with 3km here and see how well this goes
        pacc = 300000 # in cm (3 km)

        # GPS week number
        # FIXME: The Global Positioning System (GPS) epoch is January 6, 1980 UTC.
        epoch = datetime(1980, 1, 6)
        now = datetime.utcnow()

        gpstime = (now - epoch)

        # Week number
        wn = gpstime.days / 7

        try:
            leapsecs = self.aidingData["hui"]["UTC_LS"]
        except:
            # If we don't have current leap seconds yet assume 14 seconds.
            leapsecs = 14

        # GPS time of week
        towdelta = gpstime - timedelta(weeks=wn)
        tow = (towdelta.days * 86400 + towdelta.seconds + leapsecs) * 1000

        # Time accuracy needs to be changed, because the RTC is imprecise
        tacc = 60000 # in ms (1 minute)

        # We don't want the position to be valid if we don't know it
        if pos is None:
            flags = 0x02
        else:
            flags = 0x03

        # Feed GPS with position and time
        self.send("AID-INI", 48, {"X" : pos.get("x", 0) , "Y" : pos.get("y", 0) , "Z" : pos.get("z", 0), \
                  "POSACC" : pacc, "TM_CFG" : 0 , "WN" : wn , "TOW" : tow , "TOW_NS" : 0 , \
                  "TACC_MS" : tacc , "TACC_NS" : 0 , "CLKD" : 0 , "CLKDACC" : 0 , "FLAGS" : flags })

        if self.aidingData.get( "hui", None ):
            self.send("AID-HUI", 72, self.aidingData["hui"])

        # Feed gps with almanac
        if self.aidingData.get( "almanac", None ):
            for k, a in self.aidingData["almanac"].iteritems():
                logger.debug("Loaded almanac for SV %d" % a["SVID"])
                self.send("AID-ALM", 40, a);

        # Don't feed gps with ephemeris as this seems to screw up the chip and significantly lengthens
        # TTFF
        #if self.aidingData.get( "ephemeris", None ):
        #    for k, a in self.aidingData["ephemeris"].iteritems():
        #        logger.debug("Loaded ephemeris for SV %d" % a["SVID"])
        #        self.send("AID-EPH", 104, a);

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

    def handle_AID_HUI( self, data ):
        data = data[0]
        self.aidingData["hui"] = data

    def requestHuiTimer( self ):
        self.send( "AID-HUI", 0, {} )
        return True

#vim: expandtab
