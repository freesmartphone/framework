#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.option
Module: mediator
"""

from ogsmd.modems.abstract import mediator

# Ok, now this is a bit of magic...:
# We suck everything from the abstract mediator into this and overload on-demand.
# Think inheritage on a module-base... :M:

import types

for key, val in mediator.__dict__.items():
    #print key, "=", type( val )
    if type( val ) == types.TypeType:
        execstring = "global %s; %s = mediator.%s" % ( key, key, key )
        #print execstring
        exec execstring
del mediator

# add overrides here

