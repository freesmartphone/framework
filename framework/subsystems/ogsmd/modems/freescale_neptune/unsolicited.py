#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later
"""

from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

#=========================================================================#
class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )

    #
    # GSM standards
    #

    # EZX does not honor +CRM, hence +CRING is not being sent
    def plusCRING( self, calltype ):
        pass

    # +CLIP: "+4969123456789",145
    def plusCLIP( self, righthandside ):
        pass

    # +CCWA:
    def plusCCWA( self, righthandside ):
        pass

    # +CESS: 3, 14
    def plusCESS( self, righthandside ):
        print "EZX: CESS", righthandside

    # +CSSU: 2,,"",128
    # +CSSU: 10
    def plusCSSU( self, righthandside ):
        print "EZX: CSSU", righthandside
        values = safesplit( righthandside, ',' )
        if len( values ) == 4:
            code, index, number, type_ = values
        else:
            code = values[0]
            #
            # ...
            #

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
        """
        indicator, value = ( int(x) for x in safesplit( righthandside, ',' ) )

        try:
            method = getattr( self, "CIEV_%d" % indicator )
        except AttributeError:
            print "EZX: unhandled CIEV", indicator, value
        else:
            method( value )

    def CIEV_0( self, chargelevel ):
        print "EZX: CHARGE LEVEL:", chargelevel

    def CIEV_1( self, signallevel ):
        self._object.SignalStrength( 20*signallevel )
        print "EZX: SIGNAL: ", signallevel

    def CIEV_2( self, service ):
        print "EZX: SERVICE:", bool(service)

    def CIEV_3( self, present ):
        print "EZX: CALL PRESENT:", bool(present)
        self._syncCallStatus( "CIEV" )

    def CIEV_4( self, voicemail ):
        print "EZX: VOICEMAIL:", bool(voicemail)

    def CIEV_5( self, voice_activity ):
        print "EZX: VOICE ACTIVITY:", bool(voice_activity)

    def CIEV_6( self, call_progress ):
        print "EZX: CALL PROGRESS:", call_progress

    def CIEV_7( self, roaming ):
        print "EZX: ROAMING:", roaming
        self._object.modem.setData( "network:roaming", bool(roaming) )

    #
    # Motorola EZX proprietary
    #

    # RING: 1
    def RING( self, calltype ):
        self._syncCallStatus( "RING" )

    # +EOPER: 5,"262-03"
    # +EOPER: 7
    # 5 = home
    # 7 = unregistered

    def plusEOPER( self, righthandside ):
        print "EOPER:", righthandside
        values = safesplit( righthandside, ',' )
        status = {}
        if len( values ) == 1:
            status["registration"] = "unregistered"
        else:
            # FIXME: This is not correct. Need to listen for the roaming status as well
            roaming = self._object.modem.data( "roaming", False )
            status["registration"] = "roaming" if roaming else "home"
            status["provider"] = values[1]
        self._object.Status( status )

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
        print "EZX: AT ERROR FROM CLCC", error

