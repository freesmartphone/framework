#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.ericsson_F3507g
Module: modem
"""

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.ericsson_F3507g"

THINKPAD_POWER_PATH="/sys/bus/platform/devices/thinkpad_acpi/wwan_enable"

import mediator

from ..abstract.modem import AbstractModem

from .channel import EricssonChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.helpers import writeToFile

#=========================================================================#
class EricssonF3507g( AbstractModem ):
#=========================================================================#

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        self._charsets = { \
            "DEFAULT":      "gsm_ucs2",
            "PHONEBOOK":    "gsm_ucs2",
            "USSD":         "gsm_ucs2",
            }
        # One line for unsolicited messages and modem communication
        # ttyACM1 will be used for data and ttyACM2 will be used for GPS data
        self._channels["SINGLE"] = EricssonChannel( self.pathfactory, "/dev/ttyACM0", modem=self )
        # configure channel
        self._channels["SINGLE"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

        self._data["pppd-configuration"] = [ \
            "115200",
            "nodetach",
            "crtscts",
            "noipdefault",
            ":10.0.0.1",
            "local",
            'defaultroute',
            'debug',
            'hide-password',
            'ipcp-accept-local',
            #"lcp-echo-failure", "10",
            #"lcp-echo-interval", "3",
            "noauth",
            #"demand",
            "noipdefault",
            "novj",
            "novjccomp",
            "persist",
        ]



    def open( self, on_ok, on_error ):
        """
        Power on modem
        """
        writeToFile( THINKPAD_POWER_PATH, "1" )
        # call default implementation (open all channels)
        AbstractModem.open( self, on_ok, on_error )

    def close( self ): # SYNC
        """
        Power down modem
        """
        # call default implementation (closing all channels)
        AbstractModem.close( self )
        writeToFile( THINKPAD_POWER_PATH, "0" )

    def channel( self, category ):
        return self._channels["SINGLE"]

    def pathfactory( self, name ):
        return name

    def dataPort( self ):
        # FIXME remove duplication and just use pathfactory
        return "/dev/ttyACM1"
