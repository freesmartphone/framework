#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: mediator
"""

__version__ = "0.9.9.1"

from ogsmd.modems.abstract import mediator
from ogsmd.gsm import error, const
import types

import logging
logger = logging.getLogger( "ogsmd" )

#=========================================================================#
# Ok, now this is a bit of magic...:
# We suck everything from the abstract mediator into this and overload on-demand.
# Think inheritage on a module-base... :M:
#=========================================================================#
for key, val in mediator.__dict__.items():
    #print key, "=", type( val )
    if type( val ) == types.TypeType:
        execstring = "global %s; %s = mediator.%s" % ( key, key, key )
        #print execstring
        exec execstring
del mediator

#=========================================================================#
class CbSetCellBroadcastSubscriptions( CbSetCellBroadcastSubscriptions ): # s
#=========================================================================#
    # reimplemented for special TI Calypso %CBHZ handling
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            CbMediator.responseFromChannel( self, request, response )
        else:
            firstChannel = 0
            lastChannel = 0
            if self.channels == "all":
                firstChannel = 0
                lastChannel = 999
            elif self.channels == "none":
                pass
            else:
                if "-" in self.channels:
                    first, last = self.channels.split( '-' )
                    firstChannel = int( first )
                    lastChannel = int( last )
                else:
                    firstChannel = lastChannel = int( self.channels )

            logger.debug( "listening to cell broadcasts on channels %d - %d" % ( firstChannel, lastChannel ) )
            homezone = firstChannel <= 221 <= lastChannel
            self._object.modem.setData( "homezone-enabled", homezone )
            if homezone:
                self._commchannel.enqueue( "%CBHZ=1" )
            else:
                self._commchannel.enqueue( "%CBHZ=0" )
            self._ok()

#=========================================================================#
class CallInitiate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        # check parameters
        if self.calltype not in const.PHONE_CALL_TYPES:
            self._error( error.InvalidParameter( "invalid call type. Valid call types are: %s" % const.PHONE_CALL_TYPES ) )
            return
        for digit in self.number:
            if digit not in const.PHONE_NUMBER_DIGITS:
                self._error( error.InvalidParameter( "invalid number digit. Valid number digits are: %s" % const.PHONE_NUMBER_DIGITS ) )
                return
        # do the work
        if self.calltype == "voice":
            dialstring = "%s;" % self.number
        else:
            dialstring = self.number

        line = callHandler.initiate( dialstring, self._commchannel )
        if line is None:
            self._error( error.CallNoCarrier( "unable to dial" ) )
        else:
            self._ok( line )

#=========================================================================#
class CallRelease( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.release( self.index, self._commchannel ) is not None:
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to release" ) )

#=========================================================================#
class CallReleaseAll( CallMediator ):
#=========================================================================#
    def trigger( self ):
        # need to use misc channel here, so that it can also work during outgoing call
        # FIXME might rather want to consider using the state machine after all (see below)
        callHandler.releaseAll( self._object.modem.channel( "MiscMediator" ) )
        self._ok()

#=========================================================================#
class CallActivate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.activate( self.index, self._commchannel ) is not None:
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to activate" ) )

#=========================================================================#
class CallHoldActive( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.hold( self._commchannel ) is not None:
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to hold" ) )

#=========================================================================#
class CallHandler( object ):
#=========================================================================#
    def __init__( self, dbus_object ):
        self._object = dbus_object
        self._calls = {}
        self._calls[1] = { "status":"release" }
        self._calls[2] = { "status":"release" }

    def _updateStatus( self, callId ):
        """send dbus signal indicating call status for a callId"""
        self._object.CallStatus( callId, self._calls[callId]["status"], self._calls[callId] )

    def initiate( self, dialstring, commchannel ):
        return self.feedUserInput( "initiate", dialstring, commchannel )

    def activate( self, index, commchannel ):
        return self.feedUserInput( "activate", index=index, channel=commchannel )

    def release( self, index, commchannel ):
        return self.feedUserInput( "release", index=index, channel=commchannel )

    def releaseAll( self, commchannel ):
        return self.feedUserInput( "dropall", channel=commchannel )

    def hold( self, commchannel ):
        return self.feedUserInput( "hold", channel=commchannel )

    def ring( self ):
        for callId, info in self._calls.items():
            if info["status"] == "incoming":
                self._updateStatus( callId )
                break # can't be more than one call incoming at once (GSM limitation)
                # FIXME is the above comment really true?

    def statusChangeFromNetwork( self, callId, info ):
        self._calls[callId].update( info )
        if self._calls[callId]["status"] == "release":
            self._calls[callId] = { "status":"release" }
        self._updateStatus( callId )

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
        print "AT RESPONSE FROM CHANNEL=", response

    def errorFromChannel( self, request, response ):
        print "AT ERROR FROM CHANNEL=", response

    #
    # synchronize status
    #
    def syncStatus( self, request, response ):
        CallListCalls( self._object, self.syncStatus_ok, self.syncStatus_err )

    def syncStatus_ok( self, calls ):
        assert len( calls ) == 1, "unhandled case"
        # synthesize status change from network
        callid, status, properties = calls[0]
        self.statusChangeFromNetwork( callid, {"status": status} )

    def syncStatus_err( self, request, error ):
        print "AT ERROR FROM CHANNEL=", error

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
            commchannel.enqueue( "D%s" % dialstring, self.responseFromChannel, self.errorFromChannel )
            return 1

    def state_incoming_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'H' )
            return True
        elif action == "activate" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'A' )
            return True

    def state_outgoing_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].cancelCurrentCommand()
            return True

    def state_active_release( self, action, *args, **kwargs ):
        if action == "release" and kwargs["index"] == 1:
            kwargs["channel"].enqueue( 'H' )
            return True
        elif action == "hold":
            # put active call on hold without accepting any waiting or held
            # this is not supported by all modems / networks
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
        elif action == "activate":
            if kwargs["index"] == 2:
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
        return state_active_held( self, action, *args, **kwargs )

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

#=========================================================================#
def createCallHandler( dbus_object ):
#=========================================================================#
    # FIXME now that we have resources and the modem will be instanciated
    # more than once, we should probably get rid of the singleton.
    global callHandler
    if callHandler is None:
        callHandler = CallHandler( dbus_object )
    else:
        logger.warning( "Attempting to create the call handler more than once." )

#=========================================================================#
callHandler = None
#=========================================================================#

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
