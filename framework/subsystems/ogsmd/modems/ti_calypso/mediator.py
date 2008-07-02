#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: mediator
"""

from ogsmd.modems.abstract import mediator
from ogsmd.gsm import error
import types

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
class CallInitiate( CallMediator ):
#=========================================================================#
    def trigger( self ):
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
class CallActivate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.activate( self.index, self._commchannel ) is not None:
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to activate" ) )

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

    def ring( self ):
        for callId, info in self._calls.items():
            if info["status"] == "incoming":
                self._updateStatus( callId )
                break # can't be more than one call incoming at once (GSM limitation)

    def statusChangeFromNetwork( self, callId, info ):
        self._calls[callId].update( info )
        if self._calls[callId]["status"] == "release":
            self._calls[callId] = { "status":"release" }
        self._updateStatus( callId )

    def feedUserInput( self, action, *args, **kwargs ):
        # simple actions
        if action == "dropall":
            kwargs["channel"].enqueue( 'H' )
            return True
        try:
            state = "state_%s_%s" % ( self._calls[1]["status"], self._calls[2]["status"] )
            method = getattr( self, state )
        except AttributeError:
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
    global callHandler
    assert callHandler is None, "call handler created more than once"
    callHandler = CallHandler( dbus_object )

#=========================================================================#
callHandler = None
#=========================================================================#

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
