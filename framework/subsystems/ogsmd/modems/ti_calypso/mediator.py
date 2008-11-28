#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: mediator
"""

__version__ = "1.0.0"

from ogsmd.modems.abstract.mediator import *

import logging
logger = logging.getLogger( "ogsmd" )

#=========================================================================#
class CbSetCellBroadcastSubscriptions( CbSetCellBroadcastSubscriptions ): # s
#=========================================================================#
    # reimplemented for special TI Calypso %CBHZ handling
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            CbMediator.responseFromChannel( self, request, response )
        else:
            firstChannel = 0
            lastChannel = 0
            if self.channels == "all":
                firstChannel = 0
                lastChannel = 999
            elif self.channels == "none":
                pass
            else:
                if "-" in self.channels:
                    first, last = self.channels.split( '-' )
                    firstChannel = int( first )
                    lastChannel = int( last )
                else:
                    firstChannel = lastChannel = int( self.channels )

            logger.debug( "listening to cell broadcasts on channels %d - %d" % ( firstChannel, lastChannel ) )
            homezone = firstChannel <= 221 <= lastChannel
            self._object.modem.setData( "homezone-enabled", homezone )
            if homezone:
                self._commchannel.enqueue( "%CBHZ=1" )
            else:
                self._commchannel.enqueue( "%CBHZ=0" )
            self._ok()

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
