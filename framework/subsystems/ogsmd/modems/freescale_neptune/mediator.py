#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: mediator
"""

__version__ = "0.5.0.0"
MODULE_NAME = "ogsmd.modems.freescale_neptune.mediator"

from ogsmd.modems.abstract import *
from ogsmd.gsm.decor import logged
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

import logging
logger = logging.getLogger( MODULE_NAME )

# add overrides here

# FIXME probably not the right place and way to do that
import re

# modem violating 05.05 here
# the ',' before the name was not supposed to be optional
# +CMGL: 6,1,125
PAT_SMS_PDU_HEADER = re.compile( '(?P<index>\d+),(?P<status>\d+)(?:,"(?P<name>[^"]*)")?,(?P<pdulen>\d+)' )

# modem violating 05.05 here:
# the ',' before the name was not supposed to be optional
# +CMGR: 1,155
PAT_SMS_PDU_HEADER_SINGLE = re.compile( '(?P<status>\d+)(?:,"(?P<name>[^"]*)")?,(?P<pdulen>\d+)' )

const.PAT_SMS_PDU_HEADER = PAT_SMS_PDU_HEADER
const.PAT_SMS_PDU_HEADER_SINGLE = PAT_SMS_PDU_HEADER_SINGLE


#=========================================================================#
class DeviceGetInfo( DeviceMediator ):
#=========================================================================#
    """
    Modem not implementing any of +CGMR;+CGMM;+CGMI -- only +CGSN is supported
    """
    def trigger( self ):
        self._commchannel.enqueue( "+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )
        else:
            result = { "manufacturer": "Motorola",
                       "model": "Neptune Freescale Modem",
                       "imei": self._rightHandSide( response[0] ).strip( '"' ) }
            self._ok( result )

#=========================================================================#
class SimSendAuthCode( SimMediator ):
#=========================================================================#
    """
    Modem violating GSM 07.07 here.

    Format seems to be +CPIN=<number>,"<PIN>", where 1 is PIN1, 2 may be PIN2 or PUK1
    """
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

#=========================================================================#
class SimListPhonebooks( SimMediator ):
#=========================================================================#
    """
    Modem not supporting +CPBS=? here, but supporting the phonebooks "SM" and "ON".

    Workaround until the abstract mediator implements traversing through
    the list of known phonebooks trying to select them.
    """
    def trigger( self ):
        self._ok( "contacts own".split() )

#=========================================================================#
class NetworkGetStatus( NetworkMediator ):
#=========================================================================#
    """
    Modem violating GSM 07.07 here. No matter which answering format you specify
    with +COPS=..., +COPS? will always return the numerical ID of the provider
    as a string. We might have +ESPN? to the rescue, but that always returns
    an empty string for me. So until this is cleared, we have to use PLNM matching.

    Oh, by the way, +CREG? is not implemented either.
    """
    def trigger( self ):
        request, response, error = yield( "+CSQ" )
        result = {}
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result["strength"] = const.signalQualityToPercentage( int(safesplit( self._rightHandSide( response[0] ), ',' )[0]) ) # +CSQ: 22,99

        request, response, error = yield( "+COPS?" )
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                values = safesplit( self._rightHandSide( response[0] ), ',' )
                if len( values ) < 3:
                    result["mode"] = const.REGISTER_MODE[int(values[0])]
                    result["registration"] = "unregistered"
                else:
                    result["mode"] = const.REGISTER_MODE[int(values[0])]
                    roaming = self._object.modem.data( "roaming", False )
                    result["registration"] = "roaming" if roaming else "home"
                    result[ "provider"] = values[2].strip( '"' )

        self._ok( result )

#
# CB Mediators
#

#=========================================================================#
class CbGetCellBroadcastSubscriptions( CbMediator ): # s
#=========================================================================#
    """
    Modem violating 05.05 here, with +CSCB we can only specify whether
    CB messages are accepted or not at all.
    """
    def trigger( self ):
        request, response, error = yield( "+CSCB?" )
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK":
                self.responseFromChannel( request, response )
            else:
                rhs = self._rightHandSide( response[0] )
                if rhs == "1":
                    self._ok( "none" )
                else:
                    self._ok( "all" )

#=========================================================================#
class CbSetCellBroadcastSubscriptions( CbMediator ):
#=========================================================================#
    """
    Modem violating 05.05 here, with +CSCB we can only specify whether
    CB messages are accepted or not all.
    """
    def trigger( self ):
        if self.channels != "none":
            message = '0'
        else:
            message = '1'
        self._commchannel.enqueue( "+CSCB=%s" % message, self.responseFromChannel, self.errorFromChannel )
