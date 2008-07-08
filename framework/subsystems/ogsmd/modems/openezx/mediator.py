#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.openezx
Module: mediator
"""

from ogsmd.modems.abstract import mediator
from ogsmd.gsm.decor import logged

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

#=========================================================================#
class SimSendAuthCode( SimMediator ):
#=========================================================================#
    """EZX violating GSM 07.07 here."""
    def trigger( self ):
        self._commchannel.enqueue( '+CPIN=1,"%s"' % self.code, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
            # send auth status signal
            if response[0].startswith( "+CPIN" ):
                self._object.AuthStatus( self._rightHandSide( response[0] ) )
        else:
            SimMediator.responseFromChannel( self, request, response )
