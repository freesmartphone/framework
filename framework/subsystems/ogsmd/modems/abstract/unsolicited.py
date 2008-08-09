#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later

Package: ogsmd.modems.abstract
Module: unsolicited
"""

from ogsmd.gsm.decor import logged
from ogsmd.gsm import const
from ogsmd.helpers import safesplit

#=========================================================================#
class AbstractUnsolicitedResponseDelegate( object ):
#=========================================================================#

    def __init__( self, dbus_object, mediator ):
        self._object = dbus_object
        self._mediator = mediator
        self.lac = None
        self.cid = None

    def _sendStatus( self ):
        self._object.Status( self.operator, self.register, self.strength )

    #
    # unsolicited callbacks (alphabetically sorted, please keep it that way)
    #

    # PDU mode: +CBM: 88\r\n001000DD001133DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100
    # or in text mode:
    # +CBM: 16,221,0,1,1\r\n347747555093\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\r\n"
    def plusCBM( self, righthandside, pdu ):
        """
        Cell Broadcast Message
        """
        values = safesplit( righthandside, ',' )
        if len( values ) == 1:
            sn = eval( "0x%s" % pdu[0:4] )
            mid = eval( "0x%s" % pdu[4:8] )
            dcs = eval( "0x%s" % pdu[8:9] )
            page = eval( "0x%s" % pdu[9:10] )
            # FIXME convert PDU to text
            channel = mid
            data = pdu[10:]
        elif len( values ) == 5:
            sn, mid, dcs, page, pages = values
            channel = int(mid)
            data = pdu
        else:
            assert False, "unhandled +CBM cell broadcast notification"
        self._object.IncomingCellBroadcast( channel, data )

    # +CLIP: "+496912345678",145,,,,0
    def plusCLIP( self, righthandside ):
        """
        Connecting Line Identification Presence
        """
        number, ntype, rest = safesplit( righthandside, ',', 2 )
        number = number.replace( '"', '' )
        self._mediator.Call.clip( self._object, const.phonebookTupleToNumber( number, int(ntype ) ) )

    # +CMTI: "SM",7
    def plusCMTI( self, righthandside ):
        """
        Message Transfer Indication
        """
        storage, index = safesplit( righthandside, ',' )
        if storage != '"SM"':
            assert False, "unhandled +CMTI message notification"
        self._object.NewMessage( int(index) )

    # +CREG: 1,"000F","032F"
    def plusCREG( self, righthandside ):
        """
        Network Registration
        """
        values = safesplit( righthandside, ',' )
        self.register = const.REGISTER_STATUS[int(values[0])]
        if len( values ) == 3:
            self.lac = values[1].strip( '"' )
            self.cid = values[2].strip( '"' )

        self._mediator.NetworkGetStatus( self._object, self.statusOK, self.statusERR )

    # +CRING: VOICE
    def plusCRING( self, calltype ):
        """
        Incoming call
        """
        if calltype == "VOICE":
            self._mediator.Call.ring( self._object, calltype )
        elif category == "UnsolicitedMediator":
            return self._channels["UNSOL"]
        else:
            assert False, "unhandled call type"

    # +CUSD: 0," Aktuelles Guthaben: 10.00 EUR.",0'
    def plusCUSD( self, righthandside ):
        """
        Incoming USSD result
        """

        # FIXME needs to be adjusted for PDU mode

        values = safesplit( righthandside, ',' )
        if len( values ) == 1:
            mode = const.NETWORK_USSD_MODE[int(values[0])]
            self._object.IncomingUssd( mode, "" )
        elif len( values ) == 3:
            mode = const.NETWORK_USSD_MODE[int(values[0])]
            message = values[1].strip( '" ' )
            self._object.IncomingUssd( mode, message )
        else:
            assert False, "unknown format"
    #
    # helpers
    #

    def statusOK( self, status ):
        if self.lac is not None:
            status["lac"] = self.lac
        if self.cid is not None:
            status["cid"] = self.cid
        self._object.Status( status ) # send dbus signal

    def statusERR( self, values ):
        print "error... ignoring"
