#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.qualcomm_msm
Module: unsolicited
"""

from ..abstract.unsolicited import AbstractUnsolicitedResponseDelegate

class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):

    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )

