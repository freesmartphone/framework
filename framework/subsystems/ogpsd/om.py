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

import logging
logger = logging.getLogger('ogpsd')

class GTA02Device( UBXDevice ):
    """GTA02 specific GPS device"""

    def __init__( self, bus, gpschannel ):
        self.power = False
        super( GTA02Device, self ).__init__( bus, gpschannel )

    def configure(self):
        # Reset the device
        #self.send("CFG-RST", 4, {"nav_bbr" : 0xffff, "Reset" : 0x01})

#        self.send("CFG-NAV2", 0, [])
#        self.send("CFG-FXN", 36, {"flags" : 2, "t_on" : 1000, "t_off" : 10000,
#            "t_acq" : 50000, "t_acq_off" : 50000,
#            "t_reacq" : 200000, "t_reacq_off" : 300000, "base_tow" : 0})

        super( GTA02Device, self ).configure()

#    def handle_CFG_NAV2(self, data):
#        data = data[0]
#
#        if data["MinCN0Initial"] != 10:
#            # 2 - Pedestrian / 3 - Automotive
#            data["Platform"] = 2
#            data["MinCN0Initial"] = 10
#            data["MinCN0After"] = 8
#
#            self.send("CFG-NAV2", 40, data)

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "b", "" )
    def SetPower( self, power ):
        if self.power == power:
            return

        logger.debug( "Setting GPS Power to %s" % power )
        if not power:
            self.deconfigure()

        proxy = self.bus.get_object( "org.freesmartphone.odeviced" , "/org/freesmartphone/Device/PowerControl/GPS" )
        gps = dbus.Interface( proxy, "org.freesmartphone.Device.PowerControl" )
        gps.SetPower( power, reply_handler=self._replyCallback, error_handler=self._errorCallback )

    def _replyCallback( self ):
        self.power = not self.power

        if self.power:
            self.configure()

    def _errorCallback( self, e ):
        pass


#vim: expandtab
