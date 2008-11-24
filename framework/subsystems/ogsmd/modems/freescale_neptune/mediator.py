#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: mediator
"""

from ogsmd.modems.abstract import mediator
from ogsmd.gsm.decor import logged
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

# Ok, now this is a bit of magic...:
# We suck everything from the abstract mediator into this and overload on-demand.
# Think inheritage on a module-base... :M:

import types

for key, val in mediator.__dict__.items():
    #print key, "=", type( val )
    if type( val ) == types.TypeType:
        execstring = "global %s; %s = mediator.%s" % ( key, key, key )
        #print execstring
        exec execstring
del mediator

# add overrides here

#=========================================================================#
class DeviceGetInfo( DeviceMediator ):
#=========================================================================#
    """
    EZX not implementing any of +CGMR;+CGMM;+CGMI -- only +CGSN is supported
    """
    def trigger( self ):
        self._commchannel.enqueue( "+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )
        else:
            result = { "manufacturer": "Motorola",
                       "model": "Neptune Freescale Modem",
                       "imei": self._rightHandSide( response[0] ).strip( '"' ) }
            self._ok( result )

#=========================================================================#
class SimSendAuthCode( SimMediator ):
#=========================================================================#
    """
    EZX violating GSM 07.07 here.

    Format seems to be +CPIN=<number>,"<PIN>", where 1 is PIN1, 2 may be PIN2 or PUK1
    """
    def trigger( self ):
        self._commchannel.enqueue( '+CPIN=1,"%s"' % self.code, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
            # send auth status signal
            if response[0].startswith( "+CPIN" ):
                self._object.AuthStatus( self._rightHandSide( response[0] ) )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class NetworkGetStatus( NetworkMediator ):
#=========================================================================#
    """
    EZX violating GSM 07.07 here. No matter which answering format you specify
    with +COPS=..., +COPS? will always return the numerical ID of the provider
    as a string. We might have +ESPN? to the rescue, but that always returns
    an empty string for me. So until this is cleared, we have to use PLNM matching.

    Oh, by the way, +CREG? is not implemented either.
    """
    def trigger( self ):
        request, response, error = yield( "+CSQ" )
        result = {}
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result["strength"] = const.signalQualityToPercentage( int(safesplit( self._rightHandSide( response[0] ), ',' )[0]) ) # +CSQ: 22,99

        request, response, error = yield( "+COPS?" )
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                values = safesplit( self._rightHandSide( response[0] ), ',' )
                if len( values ) < 3:
                    result["mode"] = const.REGISTER_MODE[int(values[0])]
                    result["registration"] = "unregistered"
                else:
                    result["mode"] = const.REGISTER_MODE[int(values[0])]
                    roaming = self._object.modem.data( "roaming", False )
                    result["registration"] = "roaming" if roaming else "home"
                    result[ "provider"] = values[2].strip( '"' )

        self._ok( result )

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
class CallReleaseAll( CallMediator ):
#=========================================================================#
    def trigger( self ):
            callHandler.releaseAll( self._commchannel )
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
        self._calls[1] = { "status": "release" }
        self._calls[2] = { "status": "release" }

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
        # not going via state machine, since this is possible at any time
        commchannel.enqueue( "ATH" )

    def hold( self, commchannel ):
        return self.feedUserInput( "hold", channel=commchannel )

    def ring( self ):
        for callId, info in self._calls.items():
            if info["status"] == "incoming":
                self._updateStatus( callId )
                break # can't be more than one call incoming at once (GSM limitation)

    def statusChangeFromNetwork( self, callId, info ):
        print "statusChangeFromNetwork:"
        print "last status was: ", self._calls

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

        print "status now is: ", self._calls


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
    global callHandler
    assert callHandler is None, "call handler created more than once"
    callHandler = CallHandler( dbus_object )

#=========================================================================#
callHandler = None
#=========================================================================#
