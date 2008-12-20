#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2007-2008 M. Dietrich
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.abstract
Module: channel
"""

__version__ = "0.9.0"
MODULE_NAME = "ogsmd.modems.abstract.channel"

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel
import gobject

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class AbstractModemChannel( AtCommandChannel ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AtCommandChannel.__init__( self, *args, **kwargs )
        self.callback = None

        # NOTE: might make it a weak-reference, so that garbage collection
        #       does not get disturbed by the cirular modem/channel reference
        self._modem = kwargs["modem"]
        self._commands = {}
        self._populateCommands()
        self._sendCommands( "init" )

        # FIXME add warm start handling (querying CFUN and CPIN status) here

    def modemStateAntennaOn( self ):
        """
        Called, when the modem signalizes the antenna being powered on.
        """
        self._sendCommands( "antenna" )

    def modemStateSimUnlocked( self ):
        """
        Called, when the modem signalizes the SIM being unlocked.

        Override this in your concrete class to issue sending
        org.freesmartphone.GSM.SIM.ReadyStatus( true ) eventually.
        """

        # FIXME we might want to make this a 'pure virtual' method

        # don't hammer modem too early with the additional commands
        # FIXME it's actually modem specific whether we can send the command directly
        # after +CPIN: READY or not, so we should not have this here
        gobject.timeout_add_seconds( 10, self._sendCommands, "sim" )

    def modemStateSimReady( self ):
        """
        Called, when the modem signalizes the SIM data can be read.
        """
        gobject.timeout_add_seconds( 1, self._sendCommands, "sim" )

    def suspend( self, ok_callback, error_callback ):
        """
        Called, when the channel needs to configure the modem for suspending.
        """
        def done( request, response, self=self, ok_callback=ok_callback ):
            ok_callback( self )
        self._sendCommandsNotifyDone( "suspend", done )

    def resume( self, ok_callback, error_callback ):
        def done( request, response, self=self, ok_callback=ok_callback ):
            ok_callback( self )
        self._sendCommandsNotifyDone( "resume", done )

    #
    # internal API
    #
    def _sendCommands( self, state ):
        commands = self._commands[state]
        if commands:
            for command in commands:
                try:
                    commandstring = command()
                except TypeError: # not a callable
                    commandstring = command
                self.enqueue( commandstring )

    def _sendCommandsNotifyDone( self, state, done_callback ):
        # FIXME no error handling, just checking when the results are through
        commands = self._commands[state]
        if commands:
            for command in commands[:-1]:
                try:
                    commandstring = command()
                except TypeError: # not a callable
                    commandstring = command
                self.enqueue( commandstring )
            command = commands[-1]
            try:
                commandstring = command()
            except TypeError:
                commandstring = command
            self.enqueue( commandstring, done_callback, done_callback )
        else:
            done_callback( "", "" )

    def _populateCommands( self ):
        """
        Populate the command queues to be sent on modem state changes.
        """

        c = []
        # reset
        c.append( 'Z' )                 # soft reset
        c.append( 'E0V1' )              # echo off, verbose result on
        # error and result reporting reporting
        c.append( '+CMEE=1' )           # report mobile equipment errors: in numerical format
        c.append( '+CRC=1' )            # cellular result codes: enable extended format
        c.append( '+CSCS="UCS2"' )      # character set conversion: use UCS2
        c.append( '+CSDH=1' )           # show text mode parameters: show values
        c.append( '+CSNS=0' )           # single numbering scheme: voice
        # sms
        c.append( '+CMGF=0' )           # message format: enable pdu mode, disable text mode
        # unsolicited
        c.append( '+CLIP=0' )           # calling line identification presentation: disable
        c.append( '+COLP=0' )           # connected line identification presentation: disable
        c.append( '+CCWA=0' )           # call waiting: disable
        self._commands["init"] = c

        c = []
        c.append( '+CSMS=1' )           # GSM Phase 2+ commands: enable

        def sms_and_cb( self=self ):
            if self._modem.data( "sim-buffers-sms" ):
                return "+CNMI=%s" % self._modem.data( "sms-buffered-cb" )
            else:
                return "+CNMI=%s" % self._modem.data( "sms-direct-cb" )
        c.append( sms_and_cb )
        self._commands["sim"] = c

        c = []
        self._commands["antenna"] = c

        c = []
        self._commands["suspend"] = c

        c = []
        self._commands["resume"] = c

    def setIntermediateResponseCallback( self, callback ):
        assert self.callback is None, "callback already set"
        self.callback = callback

    def handleUnsolicitedResponse( self, response ):
        if self.callback is not None:
            self.callback( response )
        else:
            logger.warning( "UNHANDLED INTERMEDIATE: %s", response )
