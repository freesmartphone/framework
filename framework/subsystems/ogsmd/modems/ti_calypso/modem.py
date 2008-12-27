#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: modem

"""

__version__ = "0.9.9.6"
MODULE_NAME = "ogsmd.modems.ti_calypso"

SYSFS_CALYPSO_FLOW_CONTROL_PATH = "/sys/bus/platform/devices/neo1973-pm-gsm.0/flowcontrolled"

import mediator

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import CallChannel, UnsolicitedResponseChannel, MiscChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.channel import AtCommandChannel
from ogsmd.helpers import writeToFile

from ogsmd.helpers import killall

#=========================================================================#
class TiCalypso( AbstractModem ):
#=========================================================================#

    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # VC 1
        self._channels["CALL"] = CallChannel( self.pathfactory, "ogsmd.call", modem=self )
        # VC 2
        self._channels["UNSOL"] = UnsolicitedResponseChannel( self.pathfactory, "ogsmd.unsolicited", modem=self )
        # VC 3
        self._channels["MISC"] = MiscChannel( self.pathfactory, "ogsmd.misc", modem=self )
        # VC 4
        # FIXME pre-allocate GPRS channel for pppd?

        # configure channels
        self._channels["UNSOL"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

        # configure behaviour using special commands
        self._data["cancel-outgoing-call"] = "%CHLD=I"

    def close( self ): # SYNC
        """
        Close modem.

        Overriden for internal purposes.
        """
        # call default implementation (closing all channels)
        AbstractModem.close( self )
        # FIXME ok this is a bit hefty. gsm0710muxd has open/close dbus calls,
        # but last time I checked they weren't working.
        killall( "gsm0710muxd" )

    def channel( self, category ):
        """
        Return proper channel.

        Overridden for internal purposes.
        """
        if category == "CallMediator":
            return self._channels["CALL"]
        elif category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
        else:
            return self._channels["MISC"]

    def pathfactory( self, name ):
        """
        Allocate a new channel from the MUXer.

        Overridden for internal purposes.
        """
        muxer = self._bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        return str( muxer.AllocChannel( name, dbus_interface="org.freesmartphone.GSM.MUX" ) )

    def dataPort( self ):
        # FIXME remove duplication and just use pathfactory
        muxer = self._bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        return muxer.AllocChannel( "ogsmd.gprs", dbus_interface="org.freesmartphone.GSM.MUX" )

    def prepareForSuspend( self, ok_callback, error_callback ):
        """overridden for internal purposes"""

        # FIXME still no error handling here

        def post_ok( ok_callback=ok_callback ):
            writeToFile( SYSFS_CALYPSO_FLOW_CONTROL_PATH, "1" )
            ok_callback()

        AbstractModem.prepareForSuspend( self, post_ok, error_callback )

    def recoverFromSuspend( self, ok_callback, error_callback ):
        writeToFile( SYSFS_CALYPSO_FLOW_CONTROL_PATH, "0" )
        AbstractModem.recoverFromSuspend( self, ok_callback, error_callback )
