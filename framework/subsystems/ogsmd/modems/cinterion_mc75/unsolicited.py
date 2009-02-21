#!/usr/bin/env python
"""
The Open GSM Daemon -- Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.cinterion_mc75
Module: unsolicited
"""

from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate

class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):
    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )

        #self._callHandler.unsetHook() # we have special call handling that doesn't need stock hooks
        # No we don't (yet) :)
