#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

import dbus
from nmea import NMEADevice
from gpschannel import *

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []

		# Just open something
    channel = SerialChannel( "/dev/ttyACM0" )
    gpsdev = NMEADevice( controller.bus, channel )
    objects.append( gpsdev )

    return objects

if __name__ == "__main__":
  bus = dbus.SystemBus()

#vim: expandtab
