#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

import dbus
from gpsdevice import DummyDevice
from nmea import NMEADevice
from ubx import UBXDevice
from om import GTA02Device
from eten import EtenDevice
from gpschannel import *

NEEDS_BUSNAMES = [ "org.freedesktop.Gypsy" ]

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#

    objects = []

    devname = controller.config.getValue( "ogpsd", "device", "DummyDevice")
    channame = controller.config.getValue( "ogpsd", "channel", "GPSChannel")
    pathname = controller.config.getValue( "ogpsd", "path", "")

    channel = globals()[channame]( pathname )
    gpsdev = globals()[devname]( controller.bus, channel )
    objects.append( gpsdev )

    return objects

if __name__ == "__main__":
  bus = dbus.SystemBus()

#vim: expandtab
