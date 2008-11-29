#!/usr/bin/env python
"""
freesmartphone.org ogsmd - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems
"""

import os

import logging
logger = logging.getLogger( "ogsmd.modems" )

modemmap = { \
    "freescale_neptune": "FreescaleNeptune",
    "muxed4line":        "Muxed4Line",
    "option":            "Option",
    "sierra":            "Sierra",
    "singleline":         "SingleLine",
    "ti_calypso":        "TiCalypso",
    }

allModems = modemmap.keys
