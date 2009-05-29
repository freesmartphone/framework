#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.qualcomm_msm
Module: modem
"""

__version__ = "1.1.1"
MODULE_NAME = "ogsmd.modems.qualcomm_msm.modem"

import mediator

from ..abstract.modem import AbstractModem

from .channel import SingleLineChannel
from .unsolicited import UnsolicitedResponseDelegate

from framework.config import config

#=========================================================================#
class QualcommMsm( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # The one and only serial line
        self._channels["SINGLE"] = SingleLineChannel( self.portfactory, "ogsmd", modem=self )
        # configure channels
        self._channels["SINGLE"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

        # This modem handles setup and teardown of data connections on its own
        self._data["pppd-does-setup-and-teardown"] = False

        # This modem has a special ppp configuration
        self._data["pppd-configuration"] = [ \
            'nodetach',
            'debug',
            'defaultroute',
            "local",
            'noipdefault',
            'novj',
            "novjccomp",
            #'persist',
            'proxyarp',
            'replacedefaultroute',
            'usepeerdns',
        ]

    def channel( self, category ):
        # we do not care about a category here, we only have one channel
        return self._channels["SINGLE"]

    def portfactory( self, name ):
        return config.getValue( "ogsmd", "serial", default="/dev/smd0" )

    def dataPort( self ):
        # FIXME remove duplication and just use pathfactory
        return config.getValue( "ogsmd", "data", default="/dev/smd7" )
