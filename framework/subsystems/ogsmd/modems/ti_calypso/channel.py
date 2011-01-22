#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
(C) 2007-2008 M. Dietrich
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: channel

TI Calypso specific modem channels
"""

__version__ = "0.9.10.6"

from framework.config import config

from ogsmd.gsm.callback import SimpleCallback
from ogsmd.gsm.decor import logged
from ogsmd.modems.abstract.channel import AbstractModemChannel

import gobject

import time, itertools, select, os

import logging
logger = logging.getLogger('ogsmd')

#=========================================================================#
LOW_LEVEL_BUFFER_SIZE = 32768

#=========================================================================#
#  MMI_AEC_REQ : 0283 = Long AEC, 105 = SPENH, 187 = AEC+SPENH, 1 = STOP
#      aec_control register bits | 0  0  Sa t2|t1 g3 g2 g1|g0 e2 e1 ak|
#              bit 0 : ACK bit : set to 1 in order to warn DSP that a new command
#              is present.
#              bit 1 : enable AEC
#              bit 2 : enable SPENH (= Speech Enhancement = noise reduction)
#              bit 3 : additionnal AEC gain attenuation (lsb)
#              bit 4 : additionnal AEC gain attenuation (msb)
#              bit 5 : additionnal SPENH gain attenuation (lsb)
#              bit 6 : additionnal SPENH gain attenuation (msb)
#              bit 7 : reset trigger for AEC
#              bit 8 : reset trigger for SPENH
#              bit 9 : AEC selector 0 : short AEC, 1 : long AEC
#
#  for Short AEC        0083
#  for long AEC         0283
#  for long AEC  -6 dB  028B
#  for long AEC  -12 dB 0293
#  for long AEC  -18 dB 029B
#  for SPENH            0105
#  for SPENH -6 dB      0125
#  for SPENH -12 dB     0145
#  for SPENH -18 dB     0165
#  for BOTH             0187
#  for STOP ALL         0001 (all bits reset + ACK to 1 to warn the DSP)

AEC_NR_MAP = { \
    "short-aec":        "0083",
    "long-aec":         "0283",
    "long-aec:6db":     "028B",
    "long-aec:12db":    "0293",
    "long-aec:18db":    "029B",
    "nr":               "0105",
    "nr:6db":           "0125",
    "nr:12db":          "0145",
    "nr:18db":          "0165",
    "aec+nr":           "0187",
    "none":             "0001",
    }

def createDspCommand():
    dspMode = config.getValue( "ogsmd", "ti_calypso_dsp_mode", "aec+nr" )
    return "%N" + AEC_NR_MAP.get( dspMode, "aec+nr" )

#=========================================================================#
class CalypsoModemChannel( AbstractModemChannel ):
#=========================================================================#
    modem_communication_timestamp = 1

    def __init__( self, *args, **kwargs ):
        AbstractModemChannel.__init__( self, *args, **kwargs )

    @logged
    def _hookLowLevelInit( self ):
        """
        Low level initialization of channel.

        This is actually an ugly hack which is unfortunately
        necessary since the TI multiplexer obviously has problems
        wrt. to initialization (swallowing first bunch of commands now and then...)
        To work around this, we send 'ATE0\r\n' until we actually get an
        'OK' from the modem. We try this for 5 times, then we reopen
        the serial line. If after 10 times we still have no response,
        we assume that the modem is broken and fail.
        """
        for i in itertools.count():
            logger.debug( "(modem init... try #%d)", i+1 )
            select.select( [], [self.serial.fd], [], 0.5 )
            self.serial.write( "ATE0Q0V1\r\n" )
            r, w, x = select.select( [self.serial.fd], [], [], 0.5 )
            if r:
                try:
                    buf = self.serial.inWaiting()
                # FIXME remove catchall here
                except:
                    self.serial.close()
                    path = self.pathfactory( self.name )
                    if not path: # path is None or ""
                        return False
                    self.serial.port = str( path )
                    self.serial.open()
                    buf = self.serial.inWaiting()
                ok = self.serial.read(buf).strip()
                logger.debug( "read: %s", ok )
                if "OK" in ok or "AT" in ok:
                    break
            logger.debug( "(modem not responding)" )
            if i == 5:
                logger.debug( "(reopening modem)" )
                self.serial.close()
                path = self.pathfactory( self.name )
                if not path: # path is None or ""
                    return False
                self.serial.port = str( path )
                self.serial.open()

            if i == 10:
                logger.warning( "(can't read from modem. giving up)" )
                self.serial.close()
                return False
        logger.info( "%s: responding OK" % self )
        self.serial.flushInput()

        # reset global modem communication timestamp
        if CalypsoModemChannel.modem_communication_timestamp:
            CalypsoModemChannel.modem_communication_timestamp = time.time()

        return True

    #
    # send %CUNS on every channel as init
    #
    def _populateCommands( self ):
        AbstractModemChannel._populateCommands( self )

        self._commands["init"].append( "%CUNS=2" )

    #
    # TI Calypso has a deep sleep mode, effective after 8 seconds,
    # from which we need to wake up by sending a special character
    # (plus a small waiting time)
    #

    def _hookPreReading( self ):
        pass
        # only writes should reset the timer
        # this fixes finally ticket #435

    def _hookPostReading( self ):
        pass

    def _lowlevelRead( self ):
        return os.read( self.serial.fd, LOW_LEVEL_BUFFER_SIZE )

    def _lowlevelWrite( self, data ):
        os.write( self.serial.fd, data )

    def _hookPreSending( self ):
        if CalypsoModemChannel.modem_communication_timestamp:
            current_time = time.time()
            if current_time - CalypsoModemChannel.modem_communication_timestamp > 5:
                logger.debug( "(%s: last communication with modem was %d seconds ago. Sending EOF to wakeup)", self, int(current_time - CalypsoModemChannel.modem_communication_timestamp) )
                self.serial.write( "\x1a" )
                time.sleep( 0.4 )
            CalypsoModemChannel.modem_communication_timestamp = current_time

    def _hookPostSending( self ):
        if CalypsoModemChannel.modem_communication_timestamp:
            CalypsoModemChannel.modem_communication_timestamp = time.time()

    #
    # Since we are using a multiplexer, a hang-up condition on one channel is a good indication
    # that the underlying multiplexer died. In this case, we need to completely reinit
    #

    def _hookHandleHupCondition( self ):
        logger.warning( "HUP condition on modem channel. The multiplexer is probably dead. Launching reinit..." )
        logger.debug( "Closing the modem..." )
        self._modem.reinit()

#=========================================================================#
class CallChannel( CalypsoModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        if not "timeout" in kwargs:
            kwargs["timeout"] = 60*60
        CalypsoModemChannel.__init__( self, *args, **kwargs )
        self.callback = None

    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )
        self._commands["sim"] = []
        self._commands["antenna"] = []

    def setIntermediateResponseCallback( self, callback ):
        assert self.callback is None, "callback already set"
        self.callback = callback

    def handleUnsolicitedResponse( self, response ):
        if self.callback is not None:
            self.callback( response )
        else:
            logger.warning( "CALLCHANNEL: UNHANDLED INTERMEDIATE: %s", response )

#=========================================================================#
class MiscChannel( CalypsoModemChannel ):
#=========================================================================#
    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )
        self._commands["sim"] = []
        self._commands["antenna"] = []

#=========================================================================#
class UnsolicitedResponseChannel( CalypsoModemChannel ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        CalypsoModemChannel.__init__( self, *args, **kwargs )
        self._reenableUnsolicitedTimer = None

    def _populateCommands( self ):
        CalypsoModemChannel._populateCommands( self )

        c = self._commands["init"]
        # GSM unsolicited
        c.append( '+CLIP=1' ) # calling line identification presentation enable
        c.append( '+COLP=0' ) # connected line identification presentation: disable
        # DO NOT enable +COLP=1 on the Calypso, it will raise the chance to drop into FSO #211
        #c.append( '+COLP=1' ) # connected line identification presentation: enable
        c.append( '+CCWA=1' ) # call waiting
        c.append( "+CSSN=1,1" ) # supplementary service notifications: send unsol. code
        c.append( '+CTZU=1' ) # timezone update
        c.append( '+CTZR=1' ) # timezone reporting
        c.append( '+CREG=2' ) # registration information (NOTE not all modems support =2)
        c.append( "+CAOC=2" ) # advice of charge: send unsol. code
        # GPRS unsolicited
        c.append( "+CGEREP=2,1" )
        c.append( "+CGREG=2" )
        # calypso proprietary unsolicited
        c.append( "%CPI=3" ) # call progress indication: enable with call number ID, GSM Cause, and ALS
        c.append( "%CSCN=1,2,1,2" ) # show service change: call control service and supplementary service
        c.append( "%CSQ=1" ) # signal strength: send unsol. code
        c.append( "%CPRI=1" ) # gsm cipher indication: send unsol. code
        c.append( "%CNIV=1" )
        c.append( "%CSTAT=1" )
        # machine specific (might not be the best place here)
        c.append( '@ST="-26"' ) # audio side tone: set to minimum

        deepSleepMode = config.getValue( "ogsmd", "ti_calypso_deep_sleep", "adaptive" )
        if deepSleepMode == "never":
            c.append( "%SLEEP=2" ) # sleep mode: disable all
        else:
            c.append( "%SLEEP=4" ) # sleep mode: enable all

        c.append( createDspCommand() )

        c = self._commands["antenna"]
        c.append( "+CLVL=255" ) # audio output: set to maximum

        c = self._commands["suspend"]
        def sms_no_cb( self=self ):
            if self._modem.data( "sim-buffers-sms" ):
                return "+CNMI=%s" % self._modem.data( "sms-buffered-nocb" )
            else:
                return "+CNMI=%s" % self._modem.data( "sms-direct-nocb" )

        c.append( sms_no_cb )
        c.append( "+CTZU=0" )
        c.append( "+CTZR=0" )
        c.append( "+CREG=0" )
        c.append( "+CGREG=0" )
        c.append( "+CGEREP=0,0" )

        c.append( "%CSQ=0" )
        c.append( "%CPRI=0" )
        c.append( "%CBHZ=0" ) # home zone cell broadcast: disable

        c = self._commands["resume"]
        c.insert( 0, "+CTZU=1" )
        c.insert( 0, "+CTZR=1" )
        c.insert( 0, "+CREG=2" )
        c.insert( 0, "+CGREG=2" )
        c.insert( 0, "+CGEREP=2,1" )
        c.insert( 0, "%CSQ=1" ) # signal strength: send unsol. code
        c.insert( 0, "%CPRI=1" ) # gsm cipher indication: send unsol. code
        c.insert( 0, "%CNIV=1" )

        c += self._commands["sim"] # reenable notifications

        def homezone( self=self ):
            return "%CBHZ=1" if self._modem.data( "homezone-enabled", False ) else "%CBHZ=0"

        c.append( homezone )

    def close( self ):
        if self.delegate.checkForRecamping:
            if not self.delegate.recampingTimeout is None:
                gobject.source_remove( self.delegate.recampingTimeout )
                self.delegate.recampingTimeout = None
        CalypsoModemChannel.close( self )

    #
    # Do not send the reinit commands right after suspend, give us a bit time
    # to drain the buffer queue, as we might have been waken from GSM
    # FIXME At the end of the day, this is a workaround that tries to reduce
    # the possibilities of unsolicited responses woven in solicited responses.
    # We need to be crystal-clear here in realizing that this is a bandaid not
    # only for a conceptual problem with the AT protocol, but also our imperfect
    # AT lowlevel parser. If we would give the parser a list for every valid answer
    # forevery request, we would be able to identify unsolicited responses woven
    # in solicited reponses with much more confidence.
    # Note to self: Remember this for the forthcoming reimplementation of ogsmsd in Vala :)
    # :M:

    def resume( self, ok_callback, error_callback ):
        logger.debug( "TI Calypso specific resume handling... sending reinit in 5 seconds..." )
        def done( request, response, self=self, ok_callback=ok_callback ):
            self.reenableUnsolicitedTimer = None
            return False # mainloop: don't call me again
        self._reenableUnsolicitedTimer = gobject.timeout_add_seconds( 10, self._sendCommandsNotifyDone, "resume", done )
        ok_callback( self )

    def suspend( self, ok_callback, error_callback ):
        # check whether we suspend before the unsolicited messages have been reenabled
        if self._reenableUnsolicitedTimer is not None:
            logger.debug( "TI Calypso specific resume handling... killing reenable-unsolicited-timer." )
            gobject.source_remove( self._reenableUnsolicitedTimer )
        CalypsoModemChannel.suspend( self, ok_callback, error_callback )
