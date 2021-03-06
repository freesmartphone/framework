#!/usr/bin/env python
"""
freesmartphone.org ogsmd - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.abstract
Module: calling

New style abstract call handling
"""

__version__ = "0.9.1.4"
MODULE_NAME = "ogsmd.callhandler"

import mediator

from ogsmd import error
from ogsmd.gsm import const

from framework.patterns.processguard import ProcessGuard

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class CallHandler( object ):
#=========================================================================#

    _instance = None

    @classmethod
    def getInstance( klass, dbus_object=None ):
        if klass._instance is None and dbus_object is not None:
            klass._instance = CallHandler( dbus_object )
        return klass._instance

    def __init__( self, dbus_object ):
        self._object = dbus_object
        self._calls = {}
        self._calls[1] = { "status": "release" }
        self._calls[2] = { "status": "release" }
        # we can have at least 2 calls, more will be added when coming in

        self.unsetHook()

    def setHook( self, hook ):
        self._hook = hook

    def unsetHook( self ):
        self._hook = lambda *args, **kwargs: None

    def isBusy( self ):
        return self._calls[1]["status"] != "release" or self._calls[2]["status"] != "release"

    def status( self ):
        return self._calls[1]["status"], self._calls[2]["status"]

    #
    # additional support for data call handling with a customizable data call handler
    #
    def onActivateResult( self, request, response ):
        """
        Called after ATA
        """
        if response[0].startswith( "CONNECT" ): # data call succeeded
            self._onDataCallEstablished()

    def onInitiateResult( self, request, response ):
        """
        Called after ATDxyz
        """
        if response[0].startswith( "CONNECT" ): # data call succeeded
            self._onDataCallEstablished()

    def _onDataCallEstablished( self ):
        logger.debug( "data call established" )
        # if this is a data call, add the port where communication happens
        self.csdid = callId = 1 if self._calls[1]["status"] == "active" else 2
        self.csdchan = channel = self._object.modem.channel( "CallMediator" )
        self.statusChangeFromNetwork( callId, { "status": "connect", "port": channel.port() } )

        # check whether we have a data call handler registered
        dataCallHandler = self._object.modem.data( "data-call-handler" )
        if dataCallHandler is not None:
            self.csdchan.freeze()
            csd_commandline = dataCallHandler.split()
            if not dataCallHandler.startswith( "/bin/sleep" ): # for debugging
                csd_commandline += [ channel.port(), self._calls[callId]["direction"] ]
            self.csdproc = ProcessGuard( csd_commandline )
            logger.info( "launching csd handler as commandline %s" % csd_commandline )
            self.csdproc.execute( onExit=self._spawnedProcessDone )
        else:
            logger.info( "no csd handler registered" )

    def _spawnedProcessDone( self, pid, exitcode, exitsignal ):
        """
        Called after CSD Handler exit.
        """
        logger.info( "csd handler exited with code %d, signal %d" % ( exitcode, exitsignal ) )
        # unfreeze
        self.csdchan.thaw()
        # release call and resume normal operation
        # self.release( self.csdid, self._object.modem.channel( "MiscMediator" ) )
        self.releaseAll( self._object.modem.channel( "MiscMediator" ) )

    #
    # called from mediators
    #

    def initiate( self, dialstring, commchannel ):
        result = self.feedUserInput( "initiate", dialstring, commchannel )
        self._hook( "initiate", result )
        return result

    def activate( self, index, commchannel ):
        result = self.feedUserInput( "activate", index=index, channel=commchannel )
        self._hook( "activate", result )
        return result

    def activateConference( self, index, commchannel ):
        result = self.feedUserInput( "conference", index=index, channel=commchannel )
        self._hook( "conference", result )
        return result

    def release( self, index, commchannel ):
        result = self.feedUserInput( "release", index=index, channel=commchannel )
        self._hook( "release", result )
        return result

    def releaseAll( self, commchannel ):
        result = self.feedUserInput( "dropall", channel=commchannel )
        self._hook( "dropall", result )
        return result

    def hold( self, commchannel ):
        result = self.feedUserInput( "hold", channel=commchannel )
        self._hook( "hold", result )
        return result

    #
    # called from unsolicited response delegates
    #

    def ring( self ):
        for callId, info in self._calls.items():
            if info["status"] == "incoming":
                self._updateStatus( callId )
                break # can't be more than one call incoming at once (GSM limitation)
                # FIXME is the above comment really true?

    def statusChangeFromNetwork( self, callId, info ):
        if not self._calls.has_key(callId):
            self._calls[callId] = { "status": "release" }
        lastStatus = self._calls[callId].copy()
        self._calls[callId].update( info )

        if self._calls[callId]["status"] == "release":
            # release signal always without properties
            self._calls[callId] = { "status": "release" }

        if self._calls[callId]["status"] != "incoming":
            # suppress sending the same signal twice
            if lastStatus != self._calls[callId]:
                self._updateStatus( callId )
        else:
            self._updateStatus( callId )

    def statusChangeFromNetworkByStatus( self, status, info ):
        calls = [call for call in self._calls.items() if call[1]["status"] == status]
        if not len(calls) == 1:
            raise error.InternalException( "non-unique call state '%'" % status )
        self.statusChangeFromNetwork( calls[0][0], info )

    #
    # internal
    #

    def _updateStatus( self, callId ):
        """send dbus signal indicating call status for a callId"""
        self._object.CallStatus( callId, self._calls[callId]["status"], self._calls[callId] )

    def feedUserInput( self, action, *args, **kwargs ):
        # simple actions
        # FIXME might rather want to consider using the state machine, since that would be more clear
        if action == "dropall":
            kwargs["channel"].enqueue( 'H' )
            return True
        try:
            state = "state_%s_%s" % ( self._calls[1]["status"], self._calls[2]["status"] )
            method = getattr( self, state )
        except AttributeError:
            logger.exception( "unhandled state '%s' in state machine. calls are %s" % ( state, repr(self._calls) ) )
            raise error.InternalException( "unhandled state '%s' in state machine. calls are %s" % ( state, repr(self._calls) ) )
        else:
            return method( action, *args, **kwargs )

    #
    # deal with responses from call control commands
    #
    def responseFromChannel( self, request, response ):
        logger.debug( "response from channel to %s = %s", request, response )

    def errorFromChannel( self, request, response ):
        logger.error( "error from channel to %s = %s", request, response )

    #
    # synchronize status
    #
    def syncStatus( self, request, response ):
        mediator.CallListCalls( self._object, self.syncStatus_ok, self.syncStatus_err )

    def syncStatus_ok( self, calls ):
        if len( calls ) > 1:
            logger.warning( "unhandled case" )
            logger.warning( "calls is %s", calls)
            #return
        # synthesize status change from network
        for call in calls:
            callid, status, properties = call
            self.statusChangeFromNetwork( callid, {"status": status} )

    def syncStatus_err( self, request, error ):
        logger.error( "error from channel to %s = %s", request, error )

    #
    # state machine actions following. micro states:
    #
    # release: line idle, call has been released
    # incoming: remote party is calling, network is alerting us
    # outgoing: local party is calling, network is alerting remote party
    # active: local and remote party talking
    # held: remote party held

    # An important command here is +CHLD=<n>
    # <n>  Description
    # -----------------
    #  0   Release all held calls or set the busy state for the waiting call.
    #  1   Release all active calls.
    #  1x  Release only call x.
    #  2   Put active calls on hold (and activate the waiting or held call).
    #  2x  Put active calls on hold and activate call x.
    #  3   Add the held calls to the active conversation.
    #  4   Add the held calls to the active conversation, and then detach the local subscriber from the conversation.

    #
    # action with 1st call, 2nd call released
    #
    def state_release_release( self, action, *args, **kwargs ):
        if action == "initiate":
            dialstring, commchannel = args
            commchannel.enqueue( "D%s" % dialstring, self.onInitiateResult, self.errorFromChannel )
            return 1

    def state_incoming_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'H' )
            return True
        elif action == "activate" and kwargs["index"] == 1:
            # FIXME handle data calls here
            kwargs["channel"].enqueue( 'A', self.onActivateResult )
            return True

    def state_outgoing_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            command = self._object.modem.data( "cancel-outgoing-call" )
            kwargs["channel"].enqueue( command )
            return True

    def state_active_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'H' )
            return True
        elif action == "hold":
            # put active call on hold without accepting any waiting or held
            # this is not supported by all modems / networks
            # thus we must call syncStatus to check
            self.channel = kwargs["channel"]
            kwargs["channel"].enqueue( "+CHLD=2", self.syncStatus )
            return True

    # FIXME add state_release_active

    def state_held_release( self, action, *args, **kwargs ):
        # state not supported by all modems
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'H' )
            return True
        elif action == "activate" and kwargs["index"] == 1:
            # activate held call
            self.channel = kwargs["channel"]
            kwargs["channel"].enqueue( "+CHLD=2", self.syncStatus )
            return True
        elif action == "initiate":
            dialstring, commchannel = args
            commchannel.enqueue( "D%s" % dialstring, self.onInitiateResult, self.errorFromChannel )
            return 2

    #
    # 1st call active, 2nd call call incoming or on hold
    #
    def state_active_incoming( self, action, *args, **kwargs ):
        if action == "release":
            if kwargs["index"] == 1:
                # release active call, waiting call becomes active
                kwargs["channel"].enqueue( "+CHLD=1" )
                return True
            elif kwargs["index"] == 2:
                # reject waiting call, sending busy signal
                kwargs["channel"].enqueue( "+CHLD=0" )
                return True
        elif action == "activate":
            if kwargs["index"] == 2:
                # put active call on hold, take waiting call
                kwargs["channel"].enqueue( "+CHLD=2" )
                return True
        elif action == "conference":
            # put active call on hold, take waiting call, add held call to conversation
            kwargs["channel"].enqueue( "+CHLD=2;+CHLD=3" )
            return True

    def state_active_held( self, action, *args, **kwargs ):
        if action == "release":
            if kwargs["index"] == 1:
                # release active call, (auto)activate the held call
                kwargs["channel"].enqueue( "+CHLD=11" )
                return True
            elif kwargs["index"] == 2:
                # release held call
                kwargs["channel"].enqueue( "+CHLD=12" )
                return True
            else:
                # Fixme: we can have a 3rd call incoming that cannot be accepted, however, but still rejected
                # TI Calypso indicates the 3rd call, but refuses the index on commanding???
                logger.warning("FIXME: callid >2 (%s), don't know what to do", kwargs["index"])
        elif action == "activate":
            # put active call on hold, activate held call
            kwargs["channel"].enqueue( "+CHLD=2" )
            return True
        elif action == "conference":
            kwargs["channel"].enqueue( "+CHLD=3" )
            return True
        elif action == "connect":
            kwargs["channel"].enqueue( "+CHLD=4" )
            return True

    def state_held_active( self, action, *args, **kwargs ):
        # should be the same as the reversed state
        return self.state_active_held( action, *args, **kwargs )

    # both calls active
    def state_active_active( self, action, *args, **kwargs ):
        if action == "release":
            if kwargs["index"] == 1:
                # release only call 1
                kwargs["channel"].enqueue( "+CHLD=11" )
                return True
            elif kwargs["index"] == 2:
                kwargs["channel"].enqueue( "+CHLD=12" )
                return True
        elif action == "activate":
            if kwargs["index"] == 1:
                # put 2nd call on hold
                kwargs["channel"].enqueue( "+CHLD=21" )
                return True
            elif kwargs["index"] == 2:
                # put 1st call on hold
                kwargs["channel"].enqueue( "+CHLD=22" )
                return True
        elif action == "connect":
            kwargs["channel"].enqueue( "+CHLD=4" )
            return True

