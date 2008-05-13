#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from decor import logged

#=========================================================================#
class UnsolicitedResponseDelegate( object ):
#=========================================================================#

    @logged
    def __init__( self, object ):
        self.object = object

    def plusCREG( self, values ):
        print "REGISTRATION STATUS:", values

