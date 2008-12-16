#!/usr/bin/env python
"""
freesmartphone.org ogsmd - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems
"""

import sys

import logging
logger = logging.getLogger( "ogsmd.modems" )

theModem = None
theMediator = None

modemmap = { \
    "ericsson_F3507g":   "EricssonF3507g",
    "cinterion_mc75":    "CinterionMc75",
    "freescale_neptune": "FreescaleNeptune",
    "muxed4line":        "Muxed4Line",
    "option":            "Option",
    "sierra":            "Sierra",
    "singleline":        "SingleLine",
    "ti_calypso":        "TiCalypso",
    }

allModems = modemmap.keys

def modemFactory( modemtype ):
    logger.debug( "requested to build modem '%s'" % modemtype )
    if modemtype not in modemmap:
        return None, None

    global theMediator

    if modemtype == "singleline":
        from singleline.modem import SingleLine as Modem
        import singleline.mediator as mediator
    elif modemtype == "muxed4line":
        from muxed4line.modem import Muxed4Line as Modem
        import muxed4line.mediator as mediator
    elif modemtype == "ti_calypso":
        from ti_calypso.modem import TiCalypso as Modem
        import ti_calypso.mediator as mediator
    elif modemtype == "freescale_neptune":
        from freescale_neptune.modem import FreescaleNeptune as Modem
        import freescale_neptune.mediator as mediator
    elif modemtype == "sierra":
        from sierra.modem import Sierra as Modem
        import sierra.mediator as mediator
    elif modemtype == "option":
        from option.modem import Option as Modem
        import option.mediator as mediator
    elif modemtype == "cinterion_mc75":
        from cinterion_mc75.modem import CinterionMc75 as Modem
        import cinterion_mc75.mediator as mediator
    elif modemtype == "ericsson_F3507g":
        from ericsson_F3507g.modem import EricssonF3507g as Modem
        import ericsson_F3507g.mediator as mediator
    else:
        assert False, "must never reach this"
        sys.exit( -1 )

    global theMediator
    theMediator = mediator

    return Modem, theMediator

def currentModem():
    global theModem
    if theModem is not None:
        return theModem
    else:
        logger.error( "current modem requested before set: exiting" )
        sys.exit( -1 )

def setCurrentModem( modem ):
    global theModem
    theModem = modem
