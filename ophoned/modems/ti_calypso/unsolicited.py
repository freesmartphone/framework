#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from ..abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ophoned.gsm import const

class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):

    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )
        self._mediator.createCallHandler( self._object )

    # +CRING is only used to trigger a status update
    def plusCRING( self, calltype ):
        self._mediator.callHandler.ring()

    # +CLIP is no longer used
    def plusCLIP( self, righthandside ):
        pass

    # %CPI: 1,0,0,0,1,0,"+491772616464",145,,,0
    def percentCPI( self, righthandside ):
        """
        TI Calypso Call Progress Indication:
        callId = call number in internal call table (same as call number in CCLD)
        msgType = 0:setup, 1:disconnect, 2:alert, 3:call, 4:sync, 5:progress, 6:connected, 7:release, 8:reject (from network), 9:request
        ibt = 1, if in-band-tones enabled
        tch = 1, if traffic channel assigned
        direction = 0:MO, 1:MT, 2:CCBS, 3:MO-autoredial
        mode = 0:voice, 1:data, 2:fax, ..., 9 [see gsm spec bearer type]
        number = "number" [gsm spec]
        ntype = number type [gsm spec]
        alpha = "name", if number found in SIM phonebook [gsm spec]
        cause = GSM Network Cause [see gsm spec, section 04.08 annex H]
        line = 0, if line 1. 1, if line2.

        Typical chunks during a call:

        ... case A: incoming (MT) ...
        %CPI: 1,0,0,0,1,0,"+496912345678",145,,,0 ( setup call, MT, line one, no traffic channel yet )
        +CRING: VOICE
        %CPI: 1,0,0,1,1,0,"+496912345678",145,,,0 ( setup call, MT, line one, traffic channel assigned )
        %CPI: 1,4,0,1,1,0,"+496912345678",145,,,0 ( sync call, MT, line one, traffic channel assigned )
        %CPI: 1,0,0,1,1,0,"+496912345678",145,,,0 ( setup call, MT, line one, traffic channel assigned )
        +CRING: VOICE
        %CPI: 1,4,0,1,1,0,"+496912345678",145,,,0 ( sync call, MT, line one, traffic channel assigned )
        +CRING: VOICE

        ... case A.1: remote line hangs up ...
        %CPI: 1,1,0,1,1,0,"+496912345678",145,,,0 ( disconnect call, MT line one, traffic channel assigned )
        %CPI: 1,7,0,0,,,,,,,0 (release from network, traffic channel freed)
        (NO CARRIER, if call was connected, i.e. local accepted)

        ... case A.2: local accept (ATA) ...
        %CPI: 1,6,0,1,1,0,"+496912345678",145,,,0 ( connected call, MT, line one, traffic channel assigned )
        => from here see case A.1 or A.3

        ... case A.3: local reject (ATH) ...
        %CPI: 1,1,0,1,1,0,"+496912345678",145,,,0 ( disconnect call, MT line one, traffic channel assigned )
        %CPI: 1,7,0,0,,,,,,,0 (release from network, traffic channel freed)

        ... case B: outgoing (MO) ...
        %CPI: 1,9,0,0,0,0,"+496912345678",145,,,0 ( request call, MO, line one, no traffic channel yet )
        %CPI: 1,3,0,0,0,0,"+496912345678",145,,,0 ( call call, MO, line one, no traffic channel yet )
        %CPI: 1,4,0,1,0,0,"+496912345678",145,,,0 ( sync call, MO, line one, traffic channel assigned )
        %CPI: 1,2,1,1,0,0,"+496912345678",145,,,0 ( alert call, MO, line one, traffic channel assigned )
        (at this point, it is ringing on the other side)

        ... case B.1: remote line rejects or sends busy...
        %CPI: 1,6,0,1,0,0,"+496912345678",145,,,0 ( connect call, MO, line one, traffic channel assigned )
        (at this point, ATD returns w/ OK)
        %CPI: 1,1,0,1,0,0,"+496912345678",145,,17,0 ( disconnect call, MO, line one, traffic channel assigned )
        (at this point, BUSY(17) or NO CARRIER(16) is sent)
        %CPI: 1,7,0,0,,,,,,,0 (release from network, traffic channel freed)

        ... case B.2: remote line accepts...
        %CPI: 1,6,0,1,0,0,"+496912345678",145,,,0 ( connect call, MO, line one, traffic channel assigned )
        (at this point, ATD returns w/ OK)

        ... case B.3: local cancel ...
        ?

        """
        callId, msgType, ibt, tch, direction, mode, number, ntype, alpha, cause, line = righthandside.split( "," )

        devchannel = self._object.modem.communicationChannel( "DeviceMediator" )
        devchannel.enqueue( "+CPAS;+CEER" )

        info = {}

        if number and ntype:
            info["peer"] = const.phonebookTupleToNumber( number[1:-1], int(ntype) )
        if cause:
            info["reason"] = const.ISUP_RELEASE_CAUSE.get( int(cause), "unknown cause" )
        if line:
            info["line"] = int( line )

        if msgType == "0": # setup (MT)
            info.update ( { "status": "incoming", "direction": "incoming" } )
        elif msgType == "6": # connected (MO & MT)
            info.update( { "status": "active" } )
        elif msgType == "1": # disconnected (MO & MT)
            # FIXME try to gather reason for disconnect?
            info.update( { "status": "release" } )
        elif msgType == "8": # network reject (MO)
            info.update( { "status": "release", "reason": "no service" } )
        elif msgType == "9": # request (MO)
            info.update( { "status": "outgoing", "direction": "outgoing" } )
        if msgType in ( "01689" ):
            self._mediator.callHandler.statusChangeFromNetwork( int(callId), info )

