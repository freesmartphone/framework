#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned.modems.abstract
Module: call

# Here comes the call handling for the abstract modem, i.e. no additional
# commands available to check for network status. This was the first incarnation
# and it's broken. It should be rewritten in line with the state machine of the
# TI Calypso call handling. Account for the missing %CPI commands by calling +CCLD
# frequently to sync the state machine with the actual state of affairs.
#
# Until then I consider this code not being working at all.

"""

from ophoned.gsm.decor import logged
from .mediator import AbstractMediator

import gobject
import time

#=========================================================================#
class Call( AbstractMediator ):
#=========================================================================#
    calls = []
    index = 0
    unsolicitedRegistered = False

    @logged
    def __init__( self, dbus_object, **kwargs ):
        AbstractMediator.__init__( self, dbus_object, None, None, **kwargs )

        self._callchannel = self._object.modem.communicationChannel( "CallMediator" )

        self._status = "unknown"
        self._timeout = None
        self._index = Call.index
        Call.index += 1

        self._properties = { \
            "type": kwargs["calltype"],
            "ring": 0,
            "created": time.time(),
            "direction": kwargs["direction"],
            "duration": 0,
            "peer": "",
            "reason": "" }

        Call.calls.append( self )

        if not Call.unsolicitedRegistered:
            self._callchannel.setIntermediateResponseCallback( Call.intermediateResponse )

    def __call__( self, dialstring ):
        """Call (sic!)."""
        self._callchannel.enqueue( 'D%s' % dialstring, self.responseFromChannel, self.errorFromChannel )
        self.updateStatus( "outgoing" )
        return self._index

    def updateStatus( self, newstatus ):
        self._status = newstatus
        self._object.CallStatus( self._index, self._status, self._properties )

    def status( self ):
        return self._status

    def klingeling( self ):
        if self._timeout is not None:
            gobject.source_remove( self._timeout )
        self._timeout = gobject.timeout_add_seconds( const.TIMEOUT["RING"], self.remoteHangup )
        self._properties["ring"] += 1
        self.updateStatus( "incoming" )

    def cancel( self ):
        print "BEFORE CANCEL......................."
        self._callchannel.cancelCurrentCommand()
        print "AFTER CANCEL......................."
        self._properties["reason"] = "cancelled"
        self._die()

    def accept( self ):
        if self._timeout is not None:
            gobject.source_remove( self._timeout )
        self._callchannel.enqueue( 'A' )
        self.updateStatus( "active" )

    def remoteBusy( self ):
        self._properties["reason"] = "remote hangup"
        self._die()

    def remoteHangup( self ):
        self._properties["reason"] = "remote hangup"
        self._die()

    def reject( self ):
        # TODO can/must we differenciate between hangup and reject?
        # How do some phones send a 'BUSY' signal?
        self.hangup()

    def hangup( self ):
        self._callchannel.enqueue( 'H' )
        self._properties["reason"] = "local hangup"
        self._die()

    def remoteAccept( self ):
        self._reason = ["remote accept"]
        self.updateStatus( "active" )

    def remoteClip( self, number ):
        self._properties["peer"] = number
        self.updateStatus( "incoming" )

    def responseFromChannel( self, request, response ):
        assert self in Call.calls, "call no longer present. must have been cancelled"
        if response[-1] == "NO CARRIER":
            self._properties["reason"] = "no carrier"
            self._die()
        elif response[-1] == "OK":
            if self._properties["reason"] != "cancelled":
                self.remoteAccept()
        else:
            print "UNKNOWN RESPONSE = ", response

    def _die( self ):
        if self._timeout is not None:
            gobject.source_remove( self._timeout )
        self.updateStatus( "release" )
        Call.calls.remove( self )

    @classmethod
    @logged
    def ring( cls, dbus_object, calltype ):
        assert not len( cls.calls ) > 1, "ubermodem or broken code"
        for c in cls.calls:
            if c.status() == "incoming":
                c.klingeling()
                break
        else:
            c = Call( dbus_object, direction="incoming", calltype=calltype )
            c.klingeling()

    @classmethod
    @logged
    def clip( cls, dbus_object, number ):
        # first, check the incoming calls
        for c in cls.calls:
            if c.status() == "incoming":
                c.remoteClip( number )
                break
        else:
            # now, check the active calls
            for c in cls.calls:
                if c.status() == "active":
                    c.remoteClip( number )
                    break
            else:
                raise False, "CLIP without incoming nor active call => broken code"

    @classmethod
    @logged
    def intermediateResponse( cls, response ):
        assert len( cls.calls ) == 1, "not handling multiple calls yet"
        c = cls.calls[0]
        if response == "NO CARRIER":
            c.remoteHangup()
        elif response == "BUSY":
            c.remoteBusy()
        elif response.startswith( "CONNECT" ):
            c.talking()

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
