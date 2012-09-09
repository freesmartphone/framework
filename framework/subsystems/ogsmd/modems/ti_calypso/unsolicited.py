#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.8.5"

from .channel import createDspCommand

from framework.config import config
from ogsmd.modems import currentModem
from ogsmd.modems.abstract.unsolicited import AbstractUnsolicitedResponseDelegate
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

import gobject
import time
import logging
logger = logging.getLogger( "ogsmd" )

#=========================================================================#
class UnsolicitedResponseDelegate( AbstractUnsolicitedResponseDelegate ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractUnsolicitedResponseDelegate.__init__( self, *args, **kwargs )
        self._callHandler.unsetHook() # we have special call handling that doesn't need stock hooks

        self.fullReadyness = "unknown"
        self.subsystemReadyness = { "PHB": False, "SMS": False }

        self.checkForRecamping = ( config.getValue( "ogsmd", "ti_calypso_deep_sleep", "adaptive" ) == "adaptive" )

        if self.checkForRecamping:
            # initialize deep sleep vars
            self.lastStatus = "busy"
            self.lastTime = 0
            self.firstReregister = 0
            self.lastReregister = 0
            self.reregisterIntervals = []
            self.recampingTimeout = None

    def _checkRecampingBug( self ):
        logger.debug( "checking for TI Calypso recamping bug..." )
        logger.debug( "reregistering %d times within %d seconds. unreg/reg-Intervals are: %s" % (  len(self.reregisterIntervals), self.lastReregister-self.firstReregister, [ "%.2f" % interval for interval in self.reregisterIntervals ] ) )
        reregisterCounter = 0
        for reregisterInterval in self.reregisterIntervals:
            if reregisterInterval < 3.5: # only an immediate unregister followed by register counts as a reregister
                reregisterCounter += 1
        probeMinutes = ( self.lastReregister - self.firstReregister ) / 60.0
        recampingFactor = reregisterCounter / probeMinutes
        logger.debug( "reregistering factor: %.2f recampings/minute" % recampingFactor )
        # heuristics now
        if reregisterCounter > 5 and recampingFactor > 0.3:
            self._detectedRecampingBug()
        return False

    def _detectedRecampingBug( self ):
        logger.info( "This TI Calypso device suffers from the recamping bug. Turning off sleep mode to recover." )
        # recover from recamping bug...
        self._object.modem.channel( "MISC" ).enqueue( "%SLEEP=2" )
        # ...but launch trigger to give it another chance (it's also depending on BTS)
        if not self.recampingTimeout is None:
            # If recamping happens while there's still a timeout set warn the user and extend the timeout
            logger.warning( "Recamping bug occured, but TI Calypso is still out of deep sleep mode." )
            gobject.source_remove( self.recampingTimeout )
        self.recampingTimeout = gobject.timeout_add_seconds( 60*60, self._reactivateDeepSleep )

    def _reactivateDeepSleep( self ):
        logger.info( "Reenabling deep sleep mode on TI Calypso (giving it another chance)" )
        self.lastStatus = "busy"
        self.lastTime = 0
        self.firstReregister = 0
        self.lastReregister = 0
        self.reregisterIntervals = []
        self._object.modem.channel( "MISC" ).enqueue( "%SLEEP=4" )
        # We don't want to be called again
        self.recampingTimeout = None
        return False

    # Overridden from AbstractUnsolicitedResponseDelegate to check for the
    # TI Calypso Deep Sleep Recamping bug: http://docs.openmoko.org/trac/ticket/1024
    def plusCREG( self, righthandside ):
        # call base implementation
        AbstractUnsolicitedResponseDelegate.plusCREG( self, righthandside )
        # do we care for recamping?
        if not self.checkForRecamping:
            return
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

    # +CRING is only honored, if we didn't receive %CPI
    def plusCRING( self, calltype ):
        status = self._callHandler.status()
        if "incoming" in status:
            # looks like %CPI has been received before, ignoring
            logger.debug( "+CRING, but call status already ok: ignoring" )
            return
        else:
            logger.warning( "+CRING without previous %CPI: alerting" )
            AbstractUnsolicitedResponseDelegate.plusCRING( self, calltype )

    # +CLIP is not used on TI Calypso. See %CPI
    def plusCLIP( self, righthandside ):
        pass

    # +CCWA is not used on TI Calypso. See %CPI
    def plusCCWA( self, righthandside ):
        pass

    # +CSSU: 2,,"",128
    # 0 Forwarded call
    # 1 CUG (plus index)
    # 2 remotely put on hold
    # 3 remote hold released
    # 4 Multiparty call entered
    # 5 Call on hold has been released
    # 6 -
    # 7,8 ?
    def plusCSSU( self, righthandside ):
        code, index, number, type = safesplit( righthandside, "," )
        info = {}
        if code == "0":
            info["forwarded"] = True
        elif code == "1":
            info["cug"] = True
        elif code == "2":
            info["remotehold"] = True
        elif code == "3":
            info["remotehold"] = False
        elif code == "4":
            info["conference"] = True
        else:
            logger.info( "unhandled +CSSU code '%s'" % code )
        if info:
            # This is not failsafe since we don't know the call ID
            if code in "234":
                self._callHandler.statusChangeFromNetworkByStatus( "active", info )
            else:
                self._callHandler.statusChangeFromNetworkByStatus( "incoming", info )

    #
    # TI Calypso proprietary
    #

    # %CCCN: 0,0,A10E02010402011030068101428F0101

    # FIXME: need decoder for this
    # reponses to conference AT+CHLD=3 with one call held and one active:
    # failed (with e-plus)
    # %CCCN: 1,1,A10602010002017C
    #                     ^ fail ?
    # +CMS ERROR: 320          HEX data packet: 7e 0d ef 0d 0a 2b 43...
    #                                               ^ channel 3(MISC)? TI firmware bug? 
    # %CCCN: 0,1,A306020100020112
    #
    #
    # succeded (with D2)
    # %CCCN: 1,1,A10602010102017C
    #                     ^ ok ?
    # %CCCN: 0,1,A203020101 
    #
    #
    # call to homezone number while in homezone
    # this is sent while the call is incoming
    # %CCCN: 0,0,A10E0201000201103006810120850101
    # calling a alice sim
    # %CCCN: 0,0,A10E0201000201103006810128840107
    #
    def percentCCCN( self, righthandside ):
        direction, callId, ie = safesplit( righthandside, "," )
        # this is ASN.1 BER, but we don't want a full decoder here
        info = {}
        if ie[0:8]+ie[10:30] == "A10E020102011030068101428F01":
            info["held"] = bool( int( ie[30:32], 16 ) )
        if info:
            self._callHandler.statusChangeFromNetwork( int(callId)+1, info )

    # %CPI: 1,0,0,0,1,0,"+491772616464",145,,,0
    def percentCPI( self, righthandside ):
        """
        Call Progress Indication:
        callId = call number in internal call table (same as call number in CCLD)
        msgType = 0:setup, 1:disconnect, 2:alert, 3:call proceed, 4:sync, 5:progress, 6:connected, 7:release, 8:reject (from network), 9:request (MO Setup), 10: hold
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

        ... case C.1: first call active, second incoming and accepted (puts first on hold)
        %CPI: 1,10,0,1,0,0,"+496912345678",145,,,0
        %CPI: 2,6,0,1,1,0,"+496912345679",129,,,0

        """
        callId, msgType, ibt, tch, direction, mode, number, ntype, alpha, cause, line = safesplit( righthandside, "," )
        if msgType == "10":
            msgType ="A"  # stupid hack to have single char types

        #devchannel = self._object.modem.communicationChannel( "DeviceMediator" )
        #devchannel.enqueue( "+CPAS;+CEER" )

        info = {}

        # Report number, reason, and line, if available
        if number and ntype:
            info["peer"] = const.phonebookTupleToNumber( number[1:-1], int(ntype) )
        if cause:
            info["reason"] = const.ISUP_RELEASE_CAUSE.get( int(cause), "unknown cause" )
        if line:
            info["line"] = int( line )

        # Always report the direction
        if direction == "0":
            info.update ( { "direction": "outgoing" } )
        elif direction == "1":
            info.update ( { "direction": "incoming" } )

        # Report mode
        if mode:
            info["mode"] = const.CALL_MODE.revlookup( int(mode) )

        # Compute status

        if msgType == "0": # setup (MT)
            info.update ( { "status": "incoming" } )
        elif msgType == "6": # connected (MO & MT)
            info.update( { "status": "active" } )
        elif msgType == "1": # disconnected (MO & MT)
            # FIXME try to gather reason for disconnect?
            info.update( { "status": "release" } )
        elif msgType == "8": # network reject (MO)
            info.update( { "status": "release", "reason": "no service" } )
        elif msgType == "9": # request (MO)
            info.update( { "status": "outgoing" } )
        elif msgType == "3": # Sometimes setup is not sent?!
            info.update( { "status": info["direction"] } )
        elif msgType == "A": # hold
            info.update( { "status": "held" } )
        if msgType in "013689A":
            self._callHandler.statusChangeFromNetwork( int(callId), info )

        # DSP bandaid
        if msgType in "34":
            currentModem().channel( "MiscMediator" ).enqueue( createDspCommand() )

    # %CPRI: 1,2
    def percentCPRI( self, righthandside ):
        gsm, gprs = safesplit( righthandside, ',' )
        cipher_gsm = const.NETWORK_CIPHER_STATUS.get( int(gsm), "unknown" )
        cipher_gprs = const.NETWORK_CIPHER_STATUS.get( int(gprs), "unknown" )
        self._object.CipherStatus( cipher_gsm, cipher_gprs )

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
