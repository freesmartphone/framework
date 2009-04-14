#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.qualcomm_msm
Module: mediator
"""

from ogsmd.modems.abstract.mediator import *

__version__ = "0.1.0"
MODULE_NAME = "ogsmd.modems.qualcomm_msm.mediator"

#=========================================================================#
class PdpActivateContext( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        pdpConnection = Pdp.getInstance( self._object )
        if pdpConnection.isActive():
            self._ok()
        else:
            pdpConnection.setParameters( self.apn, self.user, self.password )
            self._commchannel.enqueue( '+CGDCONT=1,"IP","%s"' % self.apn, self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            PdpMediator.responseFromChannel( self, request, response )
        else:
            self._commchannel.enqueue( "D*99***1#", self.responseFromChannel2, self.errorFromChannel )

    def responseFromChannel2( self, request, response ):
        if response[-1] == "NO CARRIER":
            PdpMediator.responseFromChannel( self, request, response )
        else:
            pdpConnection = Pdp.getInstance( self._object )
            pdpConnection.activate()
            self._ok()
