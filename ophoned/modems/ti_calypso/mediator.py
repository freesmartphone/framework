#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned.modems.muxed4line
Module: mediator
"""

from ..modems.abstract import mediator
from ophoned.gsm import error
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

        line = callHandler.requestOutgoing( dialstring, self._commchannel )
        if line == -1:
            self._error( error.CallNoCarrier( "unable to dial" ) )
        else:
            self._ok( line )

#=========================================================================#
class CallRelease( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.release( self.index, self._commchannel ):
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to release" ) )

#=========================================================================#
class CallActivate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if callHandler.activate( self.index, self._commchannel ):
            self._ok()
        else:
            self._error( error.CallNotFound( "no such call to activate" ) )

#=========================================================================#
class CallHandler( object ):
#=========================================================================#
    def __init__( self, dbus_object ):
        self._object = dbus_object
        self._calls = {}

    def _updateStatus( self, callId ):
        """send dbus signal indicating call status for a callId"""
        self._object.CallStatus( callId, self._calls[callId]["status"], self._calls[callId] )

    def ring( self ):
        for callId, info in self._calls.items():
            if info["status"] == "incoming":
                self._updateStatus( callId )

    def statusChangeFromNetwork( self, callId, info ):
        try:
            self._calls[callId].update( info )
        except KeyError:
            self._calls[callId] = info
        self._updateStatus( callId )
        if info["status"] == "release":
            del self._calls[callId]

    def requestOutgoing( self, dialstring, commchannel ):
        if len( self._calls ) > 1:
            return -1 # we don't support more than one outgoing call
        else:
            # try callId 1
            if 1 not in self._calls:
                commchannel.enqueue( "D%s" % dialstring, self.responseFromChannel, self.errorFromChannel )
                return 1
            if 2 not in self._calls:
                commchannel.enqueue( "D%s" % dialstring, self.responseFromChannel, self.errorFromChannel )
                return 2
        return -1

    def release( self, callId, commchannel ):
        try:
            c = self._calls[callId]
        except KeyError:
            return False
        if c["status"] == "outgoing": # outgoing (not yet connected)
            commchannel.cancelCurrentCommand()
        elif c["status"] == "incoming": # incoming (not yet connected)
            commchannel.enqueue( 'H' )
        elif c["status"] == "active": # active (connected)
            commchannel.enqueue( 'H' )
        elif c["status"] == "held": # held
            raise error.InternalException( "FIXME" )
        return True

    def activate( self, callId, commchannel ):
        try:
            c = self._calls[callId]
        except KeyError:
            return False

        if len( self._calls ) > 1:
            # CHLD et. al.
            raise error.InternalException( "FIXME" )

        if c["status"] == "incoming":
            commchannel.enqueue( 'A', self.responseFromChannel, self.errorFromChannel )
        elif c["status"] == "active": # already active, ignore
            return True
        else:
            return False

    def putOnHold( self, callId, commchannel ):
        pass

    def responseFromChannel( self, request, response ):
        print "AT RESPONSE FROM CHANNEL=", response

    def errorFromChannel( self, request, response ):
        print "AT ERROR FROM CHANNEL=", response

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