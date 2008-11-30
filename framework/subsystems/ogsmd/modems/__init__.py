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
    else:
        assert False, "must never reach this"
        sys.exit( -1 )

    global theMediator
    global theModem
    theModem = Modem
    theMediator = mediator

    return theModem, theMediator
