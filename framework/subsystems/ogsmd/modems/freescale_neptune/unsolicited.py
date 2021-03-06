#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later
"""

__version__ = "0.8.2.0"
MODULE_NAME = "ogsmd.modems.freescale_neptune.unsolicited"

from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ogsmd.gsm.decor import logged
from ogsmd.gsm import const
from ogsmd.helpers import safesplit
import ogsmd.gsm.sms

import logging
logger = logging.getLogger( MODULE_NAME )

KEYCODES = { 19: "power" }

#=========================================================================#
class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )
        self._callHandler.unsetHook() # we have special call handling that doesn't need stock hooks

    #
    # GSM standards
    #

    # +CCWA:
    def plusCCWA( self, righthandside ):
        pass

    # +CESS: 3, 14
    def plusCESS( self, righthandside ):
        logger.debug("EZX: CESS", righthandside)

    def plusCIEV( self, righthandside ):
        """
        Indicator Event Reporting. Based on 3GPP TS 07.07, Chapter 8.9, but slightly extended.

        As +CIND=? gives us a hint (one of the few test commands EZX exposes), we conclude:

        0: battery charge level (0-5)
        1: signal level (0-5)
        2: service availability (0-1)
        3: call active? (0-1)
        4: voice mail (message) (0-1)
        5: transmit activated by voice activity (0-1)
        6: call progress (0-3) [0:no more in progress, 1:incoming, 2:outgoing, 3:ringing]
        7: roaming (0-2)
        8: sms storage full (0-1)
        11: ???
        20: ??? (SIM not inserted?)
        """
        indicator, value = ( int(x) for x in safesplit( righthandside, ',' ) )

        try:
            method = getattr( self, "CIEV_%d" % indicator )
        except AttributeError:
            logger.debug("EZX: unhandled CIEV", indicator, value)
        else:
            method( value )

    def CIEV_0( self, chargelevel ):
        logger.debug("EZX: CHARGE LEVEL:", chargelevel)

    def CIEV_1( self, signallevel ):
        self._object.SignalStrength( 20*signallevel )
        logger.debug("EZX: SIGNAL: ", signallevel)

    def CIEV_2( self, service ):
        logger.debug("EZX: SERVICE:", bool(service))

    def CIEV_3( self, present ):
        logger.debug("EZX: CALL PRESENT:", bool(present))
        self._syncCallStatus( "CIEV" )

    def CIEV_4( self, voicemail ):
        logger.debug("EZX: VOICEMAIL:", bool(voicemail))

    def CIEV_5( self, voice_activity ):
        logger.debug("EZX: VOICE ACTIVITY:", bool(voice_activity))

    def CIEV_6( self, call_progress ):
        logger.debug("EZX: CALL PROGRESS:", call_progress)

    def CIEV_7( self, roaming ):
        logger.debug("EZX: ROAMING:", roaming)
        self._object.modem.setData( "network:roaming", bool(roaming) )

    # +CLIP: "+4969123456789",145
    def plusCLIP( self, righthandside ):
        number, ntype = safesplit( righthandside, ',' )
        if number and ntype:
            peer = const.phonebookTupleToNumber( number[1:-1], int(ntype) )
            self._mediator.Call.clip( self._object, peer)

    # +CMT: 139
    # 07919471060040340409D041767A5C060000903021417134408A41767A5C0625DDE6B70E247D87DB69F719947683C86539A858D581C2E273195D7693CBA0A05B5E37974130568D062A56A5AF66DAED6285DDEB77BB5D7693CBA0A05B5E3797413096CC062A56A5AF66DAED0235CB683928E936BFE7A0BA9B5E968356B45CEC66C3E170369A8C5673818E757A19242DA7E7E510 
    def plusCMT( self, righthandside, pdu ):
        """
        Message Transfer Indication. Modem violating 07.07 here, the header was NOT supposed to be optional.
        """
        length = int(righthandside)
        # Now we decode the actual PDU
        sms = ogsmd.gsm.sms.SMS.decode( pdu, "sms-deliver" )
        self._object.IncomingMessage( str(sms.addr), sms.ud, sms.properties )

    # EZX does not honor +CRM, hence +CRING is not being sent
    def plusCRING( self, calltype ):
        pass

    # +CSSU: 2,,"",128
    # +CSSU: 10
    def plusCSSU( self, righthandside ):
        values = safesplit( righthandside, ',' )
        if len( values ) == 4:
            code, index, number, type_ = values
        else:
            code = values[0]
            #
            # ...
            #

    #
    # Freescale Neptune proprietary URCs
    #

    # +CCTP: 1, "+491234567"
    def plusCCTP( self, righthandside ):
        callnumber, peer = safesplit( righthandside, ',' )
        callnumber = int(callnumber)
        peer = peer.strip( '"' )
        # synthesize call status
        self._callHandler.statusChangeFromNetwork( callnumber, {"status": "outgoing", "peer":peer } )

    # +CMSM: 0
    # 0 = SIM inserted, locked
    # 3 = SIM inserted, unlocked
    def plusCMSM( self, righthandside ):
        # FIXME: Some firmware versions support +CPIN?, so we better use SimGetAuthStatus here.
        code = int( righthandside )
        if code == 0:
            self._object.AuthStatus( "SIM PIN" )
        else:
            self._object.AuthStatus( "READY" )

    # +EKEV: 19,1
    # +EKEV: 19,0
    def plusEKEV( self, righthandside ):
        values = safesplit( righthandside, ',' )
        keyname = KEYCODES.get( int( values[0] ), "unknown" )
        pressed = bool( int( values[1] ) )
        self._object.KeypadEvent( keyname, pressed )

    # +EOPER: 5,"262-03"
    # +EOPER: 7
    # 0 = busy
    # 5 = home
    # 7 = unregistered
    def plusEOPER( self, righthandside ):
        values = safesplit( righthandside, ',' )
        status = {}
        if len( values ) == 1:
            status["registration"] = "unregistered"
        else:
            # FIXME: This is not correct. Need to listen for the roaming status as well
            roaming = self._object.modem.data( "network:roaming", False )
            status["registration"] = "roaming" if roaming else "home"
            status["provider"] = values[1]
        self._object.Status( status )

    # RING: 1
    def RING( self, calltype ):
        self._syncCallStatus( "RING" )

    #
    # helpers
    #

    def _syncCallStatus( self, initiator ):
       self._mediator.CallListCalls( self._object, self._syncCallStatus_ok, self._syncCallStatus_err )

    def _syncCallStatus_ok( self, calls ):
        seen = []
        for callid, status, properties in calls:
            seen.append( callid )
            self._callHandler.statusChangeFromNetwork( callid, {"status": status} )
        # synthesize remaning calls
        if not 1 in seen:
            self._callHandler.statusChangeFromNetwork( 1, {"status": "release"} )
        if not 2 in seen:
            self._callHandler.statusChangeFromNetwork( 2, {"status": "release"} )

    def _syncCallStatus_err( self, request, error ):
        logger.warning( "AT ERROR from CLCC: %s", error )

