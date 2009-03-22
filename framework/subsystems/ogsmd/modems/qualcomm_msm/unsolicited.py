#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.qualcomm_msm
Module: unsolicited
"""

__version__ = "0.0.1.0"
MODULE_NAME = "ogsmd.modems.qualcomm_msm.unsolicited"

from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ogsmd.gsm import const
from ogsmd.helpers import safesplit
import ogsmd.gsm.sms

import logging
logger = logging.getLogger( MODULE_NAME )

class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):

    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )

    #
    # GSM standards
    #

    #
    # Proprietary URCs
    #

    # +PB_READY
    def plusPB_READY( self, righthandside ):
        self._object.ReadyStatus( True )
