#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later

Package: ogsmd.modems.abstract
Module: unsolicited
"""

__version__ = "0.9.9.5"
MODULE_NAME = "ogsmd.modems.abstract.unsolicited"

import calling, pdp

from ogsmd.gsm.decor import logged
from ogsmd.gsm import const, convert
from ogsmd.helpers import safesplit
from ogsmd.modems import currentModem
import ogsmd.gsm.sms

import logging
logger = logging.getLogger( MODULE_NAME )

import gobject

KEYCODES = {}

#=========================================================================#
class AbstractUnsolicitedResponseDelegate( object ):
#=========================================================================#

    def __init__( self, dbus_object, mediator ):
        self._object = dbus_object
        self._mediator = mediator
        self._callHandler = calling.CallHandler.getInstance( dbus_object )
        self._callHandler.setHook( self._cbCallHandlerAction )

        self.lac = None
        self.cid = None

        self._syncTimeout = None

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
        if len( values ) == 1: # PDU MODE
            cb = ogsmd.gsm.sms.CellBroadcast.decode(pdu)
            sn = cb.sn
            channel = cb.mid
            dcs = cb.dcs
            page = cb.page
            data = cb.ud
        elif len( values ) == 5: # TEXT MODE
            sn, mid, dcs, page, pages = values
            channel = int(mid)
            data = pdu
        else:
            logger.warning( "unrecognized +CBM cell broadcast notification, please fix me..." )
            return
        self._object.IncomingCellBroadcast( channel, data )

    # +CGEV: ME DEACT "IP","010.161.025.237",1
    # +CGEV: ME DETACH
    def plusCGEV( self, righthandside ):
        """
        Gprs Context Event
        """
        values = safesplit( righthandside, ',' )
        if len( values ) == 1: # detach, but we're not having an IP context online
            if values[0] == "ME DETACH":
                # FIXME this will probably lead to a zombie
                instance = pdp.Pdp.getInstance()
                if instance is not None:
                    instance.deactivate()
                # FIXME force dropping the dataport, this will probably kill the zombie
        elif len( values ) >= 3: # detach while we were attached
            pass

        # +CGREG: 2
        # +CGREG: 1,"000F","5B4F
    def plusCGREG( self, righthandside ):
        """
        Gprs Registration Status Update
        """
        charset = currentModem()._charsets["DEFAULT"]
        values = safesplit( righthandside, ',' )
        status = {}
        status["registration"] = const.REGISTER_STATUS[int(values[0])]
        if len( values ) >= 3:
            status["lac"] = values[1].strip( '"' ).decode(charset)
            status["cid"] = values[2].strip( '"' ).decode(charset)
        self._object.NetworkStatus( status )

    # +CREG: 1,"000F","032F"
    # +CREG: 1,"000F","032F",2
    def plusCREG( self, righthandside ):
        """
        Network Registration Status Update
        """
        charset = currentModem()._charsets["DEFAULT"]
        values = safesplit( righthandside, ',' )
        self.register = const.REGISTER_STATUS[int(values[0])]
        if len( values ) >= 3:
            self.lac = values[1].strip( '"' ).decode(charset)
            self.cid = values[2].strip( '"' ).decode(charset)
        self._mediator.NetworkGetStatus( self._object, self.statusOK, self.statusERR )

    # +CLIP: "+496912345678",145,,,,0
    def plusCLIP( self, righthandside ):
        """
        Connecting Line Identification Presence
        """
        number, ntype, rest = safesplit( righthandside, ',', 2 )
        number = number.replace( '"', '' )
        logger.warning( "plusCLIP not handled -- please fix me" )
        #self._mediator.Call.clip( self._object, const.phonebookTupleToNumber( number, int(ntype ) ) )

    # +CMT: "004D00690063006B006500790020007000720069",22
    # 0791947107160000000C9194712716464600008001301131648003D9B70B
    def plusCMT( self, righthandside, pdu ):
        """
        Message Transfer Indication
        """
        header = safesplit( righthandside, ',' )
        length = int(header[1])
        # Now we decode the actual PDU
        sms = ogsmd.gsm.sms.SMS.decode( pdu, "sms-deliver" )
        self._object.IncomingMessage( str(sms.addr), sms.ud, sms.properties )

    # +CDS: <PDU size>\r\n<PDU>
    def plusCDS( self, righthandside, pdu ):
        """
        Incoming delivery report
        """
        sms = ogsmd.gsm.sms.SMS.decode( pdu, "sms-status-report" )
        self._object.IncomingMessageReceipt( str(sms.addr), sms.ud, sms.properties )

        # Always acknoledge a status report right away
        sms = ogsmd.gsm.sms.SMSDeliverReport(True)
        pdu = sms.pdu()
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" )
        # XXX: Replace the lambda with an actual funtion in error case?
        commchannel.enqueue( '+CNMA=1,%i\r%s' % ( len(pdu)/2, pdu), lambda x,y: None, lambda x,y: None )

    # +CKEV: 19,1
    # +CKEV: 19,0
    def plusCKEV( self, righthandside ):
        values = safesplit( righthandside, ',' )
        keyname = KEYCODES.get( int( values[0] ), "unknown" )
        pressed = bool( int( values[1] ) )
        self._object.KeypadEvent( keyname, pressed )

    # +CMTI: "SM",7
    def plusCMTI( self, righthandside ):
        """
        Message Transfer Indication
        """
        storage, index = safesplit( righthandside, ',' )
        if storage != '"SM"':
            logger.warning( "unhandled +CMTI message notification" )
        else:
            self._object.IncomingStoredMessage( int(index) )

    # +CRING: VOICE
    # +CRING: REL ASYNC
    def plusCRING( self, calltype ):
        """
        Incoming call
        """
        self._syncCallStatus( "RING" )
        self._startTimeoutIfNeeded()

    # +CMS ERROR: 322
    def plusCMS_ERROR( self, righthandside ):
        """
        Incoming unsolicited error

        Seen, when we are using SMS in SIM-buffered mode.
        """
        errornumber = int( righthandside )
        if errornumber == 322:
            self._object.MemoryFull()

    # +CTZV: 35 (observed in Taipei, UTC+7)
    # +CTZV: 105 (observed in UTC-4)
    def plusCTZV( self, righthandside ):
        """
        Incoming Timezone Report
        """
        self._object.TimeZoneReport( const.ctzvToTimeZone( righthandside ) )

    # +CUSD: 0," Aktuelles Guthaben: 10.00 EUR.",0'
    def plusCUSD( self, righthandside ):
        """
        Incoming USSD result
        """
        charset = currentModem()._charsets["USSD"]
        values = safesplit( righthandside, ',' )
        if len( values ) == 1:
            mode = const.NETWORK_USSD_MODE[int(values[0])]
            self._object.IncomingUssd( mode, "" )
        elif len( values ) == 3:
            mode = const.NETWORK_USSD_MODE[int(values[0])]
            message = values[1].strip( '" ' ).decode(charset)
            self._object.IncomingUssd( mode, message )
        else:
            logger.warning( "Ignoring unknown format: '%s'" % righthandside )
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
        logger.warning( "statusERR... ignoring" )

    def _startTimeoutIfNeeded( self ):
        if self._syncTimeout is None:
            self._syncTimeout = gobject.timeout_add_seconds( 1, self._cbSyncTimeout )

    def _syncCallStatus( self, initiator ):
       self._mediator.CallListCalls( self._object, self._syncCallStatus_ok, self._syncCallStatus_err )

    def _syncCallStatus_ok( self, calls ):
        seen = []
        for callid, status, properties in calls:
            seen.append( callid )
            self._callHandler.statusChangeFromNetwork( callid, {"status": status} )
        # synthesize remaining calls
        if not 1 in seen:
            self._callHandler.statusChangeFromNetwork( 1, {"status": "release"} )
        if not 2 in seen:
            self._callHandler.statusChangeFromNetwork( 2, {"status": "release"} )

    def _syncCallStatus_err( self, request, error ):
        logger.warning( "+CLCC didn't succeed -- ignoring" )

    def _cbSyncTimeout( self, *args, **kwargs ):
        """
        Called by the glib mainloop while anything call-related happens.
        """
        logger.debug( "sync timeout while GSM is not idle" )
        self._syncCallStatus( "SYNC TIMEOUT" )

        if self._callHandler.isBusy():
            logger.debug( "call handler is busy" )
            return True # glib mainloop: please call me again
        else:
            logger.debug( "call handler is not busy" )
            self._syncTimeout = None
            return False # glib mainloop: don't call me again

    def _cbCallHandlerAction( self, action, result ):
        """
        Called by the call handler once a user-initiated action has been performed.
        """
        self._syncCallStatus( "MEDIATOR ACTION" )
        logger.debug( "call handler action %s w/ result %s" % ( action, result ) )
        if result is not False:
            if action == "initiate":
                first, second = self._callHandler.status()
                if first == "release":
                    self._callHandler.statusChangeFromNetwork( 1, {"status": "outgoing"} )
                else:
                    self._callHandler.statusChangeFromNetwork( 2, {"status": "outgoing"} )
            self._startTimeoutIfNeeded()
