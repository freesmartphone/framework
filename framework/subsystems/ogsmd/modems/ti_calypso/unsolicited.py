#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

import gobject
import time
import logging
logger = logging.getLogger( "ogsmd.modem.unsolicited" )

class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):

    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )
        self._mediator.createCallHandler( self._object )

        self.fullReadyness = "unknown"
        self.subsystemReadyness = { "PHB": False, "SMS": False }

        # deep sleep vars
        self.lastStatus = "busy"
        self.lastTime = 0
        self.firstReregister = 0
        self.lastReregister = 0
        self.reregisterIntervals = []

    def _checkRecampingBug( self ):
        logging.debug( "checking for TI Calypso recamping bug..." )
        logging.debug( "reregistering %d times within %d seconds. unreg/reg-Intervals are: %s" % ( len(self.reregisterIntervals), self.lastReregister-self.firstReregister, self.reregisterIntervals ) )
        reregisterCounter = 0
        for reregisterInterval in self.reregisterIntervals:
            if reregisterInterval < 3.0: # only an immediate unregister followed by register counts as a reregister
                reregisterCounter += 1
        probeMinutes = ( self.lastReregister - self.firstReregister ) / 60.0
        recampingFactor = reregisterCounter / probeMinutes
        logging.debug( "reregistering factor: %f recampings/minute" % recampingFactor )
        # heuristics now
        if reregisterCounter > 5 and recampingFactor > 4:
            self._detectedRecampingBug()
        return False

    def _detectedRecampingBug( self ):
        logging.info( "This TI Calypso device suffers from the recamping bug. Turning off sleep mode to recover." )
        # recover from recamping bug...
        self._object.modem.channel( "MISC" ).enqueue( "%SLEEP=2" )
        # ...but launch trigger to give it another chance (it's also depending on BTS)
        gobject.timeout_add_seconds( 60*60, self._reactivateDeepSleep )


    def _reactivateDeepSleep( self ):
        logging.info( "Reenabling deep sleep mode on TI Calypso (giving it another chance)" )
        self.lastStatus = "busy"
        self.lastTime = 0
        self.firstReregister = 0
        self.lastReregister = 0
        self.reregisterIntervals = []
        self._object.modem.channel( "MISC" ).enqueue( "%SLEEP=4" )

    # Overridden from AbstractUnsolicitedResponseDelegate to check for the
    # TI Calypso Deep Sleep Recamping bug: http://docs.openmoko.org/trac/ticket/1024
    def plusCREG( self, righthandside ):
        # call base implementation
        AbstractUnsolicitedResponseDelegate.plusCREG( self, righthandside )
        # check for recamping
        values = safesplit( righthandside, ',' )
        register = const.REGISTER_STATUS[int(values[0])]
        if self.lastStatus == "unregistered":
            if self.register in "home roaming".split():
                self.reregisterIntervals.append( time.time() - self.lastTime )
                if len( self.reregisterIntervals ) == 1:
                    self.firstReregister = time.time()
                gobject.idle_add( self._checkRecampingBug )
                self.lastReregister = time.time()
        self.lastStatus = register
        self.lastTime = time.time()

    # +CRING is only used to trigger a status update
    def plusCRING( self, calltype ):
        pass
        # self._mediator.callHandler.ring()

    # +CLIP is not used on TI Calypso. See %CPI
    def plusCLIP( self, righthandside ):
        pass

    # +CCWA is not used on TI Calypso. See %CPI
    def plusCCWA( self, righthandside ):
        pass

    # +CSSU: 2,,"",128
    def plusCSSU( self, righthandside ):
        code, index, number, type = safesplit( righthandside, "," )

    #
    # TI Calypso proprietary
    #

    # %CCCN: 0,0,A10E02010402011030068101428F0101
    def percentCCCN( self, righthandside ):
        direction, callId, ie = safesplit( righthandside, "," )
        # this is ASN.1 BER, but we don't want a full decoder here
        info = {}
        if ie[0:8]+ie[10:30] == "A10E020102011030068101428F01":
            info["held"] = bool( int( ie[30:32], 16 ) )
        if info:
            self._mediator.callHandler.statusChangeFromNetwork( int(callId)+1, info )

    # %CPI: 1,0,0,0,1,0,"+491772616464",145,,,0
    def percentCPI( self, righthandside ):
        """
        Call Progress Indication:
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
        callId, msgType, ibt, tch, direction, mode, number, ntype, alpha, cause, line = safesplit( righthandside, "," )

        #devchannel = self._object.modem.communicationChannel( "DeviceMediator" )
        #devchannel.enqueue( "+CPAS;+CEER" )

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

    # %CSSN: 1,0,A11502010802013B300D04010F0408AA510C0683C16423
    def percentCSSN( self, righthandside ):
        direction, transPart, ie = safesplit( righthandside, "," )

    # %CSTAT: PHB,0
    # %CSTAT: SMS,0
    # %CSTAT: RDY,1
    # %CSTAT: EONS,1
    def percentCSTAT( self, righthandside ):
        """
        TI Calypso subsystem status report

        PHB is phonebook, SMS is messagebook. RDY is supposed to be sent, after
        PHB and SMS both being 1, however it's not sent on all devices.
        EONS is completely undocumented.

        Due to RDY being unreliable, we wait for PHB and SMS sending availability
        and then synthesize a global SimReady signal.
        """
        subsystem, available = safesplit( righthandside, "," )
        if not bool(int(available)): # not ready
            if subsystem in ( "PHB", "SMS" ):
                self.subsystemReadyness[subsystem] = False
                logger.info( "subsystem %s readyness now %s" % ( subsystem, self.subsystemReadyness[subsystem] ) )
                if not self.fullReadyness == False:
                    self._object.ReadyStatus( False )
                    self.fullReadyness = False
        else: # ready
            if subsystem in ( "PHB", "SMS" ):
                self.subsystemReadyness[subsystem] = True
                logger.info( "subsystem %s readyness now %s" % ( subsystem, self.subsystemReadyness[subsystem] ) )
                newFullReadyness = self.subsystemReadyness["PHB"] and self.subsystemReadyness["SMS"]
                if newFullReadyness and ( not self.fullReadyness == True ):
                    self._object.ReadyStatus( True )
                    self.fullReadyness = True

        logger.info( "full readyness now %s" % self.fullReadyness )

    # %CSQ:  17, 0, 1
    def percentCSQ( self, righthandside ):
        """
        signal strength report
        """
        strength, snr, quality = safesplit( righthandside, "," )
        self._object.SignalStrength( const.signalQualityToPercentage( int(strength) ) ) # send dbus signal
