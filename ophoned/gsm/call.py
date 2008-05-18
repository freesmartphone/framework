#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import gobject
import const
import time

calls = []

#=========================================================================#
class Call( object ):
#=========================================================================#
    """
    A Call object encapsulates a call known to the phone server.
    Objects are created based on incoming or outgoing calls.
    """

    def __init__( self, dbus_object, status, t ):
        assert status in ( "incoming", "outgoing" ), "invalid status"
        self._object = dbus_object
        self._status = status
        self._properties = { \
        "type": t,
        "ring": 0,
        "created": time.time(),
        "direction": status,
        "duration": 0,
        "peer": "" }
        assert self not in calls, "duplicated call"
        calls.append( self )
        self.idx = calls.index( self )
        self.timeout = None
        if status == "incoming":
            self.ring()
        else:
            self._updateStatus()

    def _updateStatus( self ):
        self._object.CallStatus( self.index(), self._status, self._properties )

    def ring( self ):
        if self.timeout is not None:
            gobject.source_remove( self.timeout )
        self.timeout = gobject.timeout_add_seconds( const.TIMEOUT["RING"], self._die )
        self._properties["ring"] += 1
        self._updateStatus()

    def accept( self ):
        assert self.timeout is not None, "huh?"
        gobject.source_remove( self.timeout )
        self._object.callchannel( "A" )
        self.setStatus( "active" )

    def reject( self ):
        gobject.source_remove( self.timeout )
        self._object.callchannel( "H" )
        self._die()

    def release( self ):
        pass

    def onHold( self ):
        pass

    def setStatus( self, status ):
        self._status = status
        self._updateStatus()

    def status( self ):
        return self._status

    def isVoice( self ):
        return self._properties["type"] == "voice"

    def isData( self ):
        return self._properties["type"] == "data"

    def isIncoming( self ):
        return self._properties["direction"] == "incoming"

    def index( self ):
        return self.idx

    def _die( self ):
        calls.remove( self )

    def __del__( self ):
        self._status = "released"
        self._updateStatus()

class IncomingVoiceCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "incoming", "voice" )

class IncomingDataCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "incoming", "data" )

class IncomingFaxCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "incoming", "fax" )

class OutgoingVoiceCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "outgoing", "voice" )

class OutgoingDataCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "outgoing", "data" )

class OutgoingFaxCall( Call ):
    def __init__( self, dbus_object ):
        Call.__init__( self, dbus_object, "outgoing", "fax" )

#=========================================================================#
def _firstIncoming():
    for call in calls:
        if call.status() == "incoming":
            return call
    return None

#=========================================================================#
def handleIncomingCall( t, dbus_object ):
    call = _firstIncoming()
    if call:
        call.ring()
    else:
        if t == "VOICE":
            IncomingVoiceCall( dbus_object )
            return
        elif t == "DATA":
            IncomingDataCall( dbus_object )
            return
        assert False, "unknown call type"

#=========================================================================#
def acceptIncomingCall():
    call = _firstIncoming()
    if call:
        call.accept()
    else:
        assert False, "no incoming call available"

#=========================================================================#
def rejectIncomingCall():
    call = _firstIncoming()
    if call:
        call.reject()
    else:
        assert False, "no incoming call available"

#=========================================================================#
