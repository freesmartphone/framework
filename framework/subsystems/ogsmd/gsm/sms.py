#!/usr/bin/env python
"""
PDU parser - Python Implementation
Based on desms.py by Adam Sampson <ats@offog.org>

(C) 2008 Daniel Willman <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: pdu

"""
from ogsmd.gsm.convert import *
from ogsmd.gsm.const import CB_PDU_DCS_LANGUAGE, TP_MTI_INCOMING, TP_MTI_OUTGOING, SMS_ALPHABET_TO_ENCODING, TP_FCS
import math
from array import array
from datetime import datetime

class SMSError(Exception):
    pass

#    ** Dekodieren
#    smsobject = SMS.decode( pdu )
#    print "von", smsobject.sender(), "um", smsobject.arrivalTime(), "via" smsobject.serviceCenter(), ...
#    print "uses charset", smsobject.charset(), ...
#    ** Enkodieren
#    smsobject = encodeSMS( peer, sender, serviceCenter )
#    pdu = smsobject.pdu()
# * AbstractSms (uebernimmt codierung/decodierung)
# * SmsMessagePart (repraesentiert eine SMS "on the wire")
# * SmsMessage (repraesentiert eine -- moeglicherweise Multipart -- Nachricht)
# * Weitere, fuer spezifische SMS-Typen (Status Report) eigene Klassen? Ggfs. zu komplex.

class PDUAddress:
    @classmethod
    def guess( cls, number ):
        if number[0] == "+":
            number = number[1:]
            ntype = 1
        elif number.isdigit():
            # The type of number is unknown
            number = number
            ntype = 0
        else:
            number = number
            ntype = 5
        return cls( ntype, 1, number )

    @classmethod
    def decode( cls, bs ):
        num_type = ( bs[0] & 0x70)  >> 4
        num_plan = ( bs[0] & 0x0F )
        number = bs[1:]
        if number == []:
            number = ""
        elif num_type == 5:
            # Alphanumeric Address
            number = unpack_sevenbit( number )
            number = number.decode( "gsm_default" )

            # On some occasions when names are n*8-1 characters long
            # there are exactly 7 padding bits left which will result
            # in the "@" character being appended to the name.
            if len(number) % 8 == 0 and number[-1] == "@":
                number = number[:-1]
        else:
            number = bcd_decode( number )
            # Every occurence of the padding semi-octet should be removed
            number = number.replace( "f", "" )
            # Decode special "digits"
            number = number.translate( PDUADDR_DEC_TRANS )
        return cls( num_type, num_plan, number )

    def __init__( self, type, dialplan, number ):
        self.type = type
        self.dialplan = dialplan
        self.number = number
    def __str__( self ):
        prefix = ""
        if self.type == 1:
            prefix = "+"
        return prefix + self.number

    def pdu( self ):
        if self.type == 5:
            number = self.number.encode("gsm_default")
            enc = pack_sevenbit(number)
            length = len(enc)*2
            if (len(self.number)*7)%8 <= 4:
                length -= 1
        else:
            # Encode special "digits"
            number = str(self.number).translate(PDUADDR_ENC_TRANS)
            enc = bcd_encode(number)
            length = len(number)
        return flatten( [length, 0x80 | self.type << 4 | self.dialplan, enc] )

class SMS(object):
    @classmethod
    def decode( cls, pdu, smstype ):
        # first convert the string into a bytestream
        try:
            bytes = array('B', [ int( pdu[i:i+2], 16 ) for i in range(0, len(pdu), 2) ])
        except ValueError:
            raise SMSError, "PDU malformed"

        if smstype == "sms-submit":
            sms = SMSSubmit()
        elif smstype == "sms-deliver":
            sms = SMSDeliver()
        elif smstype == "sms-submit-report":
            sms = SMSSubmitReport()
        elif smstype == "sms-deliver-report":
            sms = SMSDeliverReport()
        elif smstype == "sms-status-repot":
            sms = SMSStatusReport()
        elif smstype == "sms-command":
            sms = SMSCommand()
        else:
            raise SMSError, "Invalid type %s" % (smstype)

        sms.parse( bytes )

        return sms

    def __init__( self ):
        self.error = []

    def _parse_sca( self, bytes, offset ):
        # SCA - Service Center address
        sca_len = bytes[offset]
        offset += 1
        if sca_len > 0:
            sca = PDUAddress.decode( bytes[offset:offset+sca_len] )
        else:
            sca = False

        return ( sca, sca_len + 1 )


    def _parse_address( self, bytes, offset ):
        # XXX: Is this correct? Can we detect the @-padding issue in address_len?
        address_len = 1 + (bytes[offset] + 1) / 2
        offset += 1
        address = PDUAddress.decode( bytes[offset:offset+address_len] )
        return ( address, address_len  + 1 )

    def _parse_userdata( self, ud_len, bytes ):
        offset = 0
        self.udh = {}
        if self.pdu_udhi:
            # Decode the headers
            udh_len =  bytes[offset]
            offset += 1
            while offset < udh_len:
                # Information Element
                iei = bytes[offset]
                offset += 1
                ie_len = bytes[offset]
                offset += 1
                ie_data = bytes[offset:offset+ie_len]
                offset += ie_len
                # FIXME
                self.udh[iei] = ie_data

        # We need to lose the padding bits before the start of the
        # seven-bit packed data, which means we need to figure out how
        # many there are...
        # See the diagram on page 58 of GSM_03.40_6.0.0.pdf.

        userdata = "".join( map( chr, bytes[offset:] ) )
        if self.dcs_alphabet == "gsm_default":
            padding_size = ((7 * ud_len) - (8 * (offset))) % 7
            userdata = unpack_sevenbit(bytes[offset:], padding_size)
            septets = ud_len - int( math.ceil( (offset*8)/7.0 ) )
            userdata = userdata[:septets]

        if not self.dcs_alphabet is None:
            try:
                self.ud = userdata.decode( self.dcs_alphabet )
            except UnicodeError, e:
                self.error.append("Userdata corrupt")
                self.ud = ""
        else:
            # Binary message
            self.data = [ ord(x) for x in userdata ]
            self.ud = "This is a binary message"



    def _getType( self ):
        return self.mtimap[self.pdu_mti]

    def _setType( self, smstype ):
        if TP_MTI_INCOMING.has_key(smstype):
            self.mtimap = TP_MTI_INCOMING
        elif TP_MTI_OUTGOING.has_key(smstype):
            self.mtimap = TP_MTI_OUTGOING
        else:
            raise SMSError, "Invalid SMS type %s" % (smstype)

        self.pdu_mti = self.mtimap[smstype]

    type = property( _getType, _setType )

    def _getDCS( self ):
        # TODO throw exceptions on invalid combinations
        if self.dcs_mwi_type is None:
            dcs = 0
            dcs |= self.dcs_compressed << 5
            if self.dcs_alphabet is None :
                dcs |= 0x1 << 2
            elif self.dcs_alphabet == "utf_16_be":
                dcs |= 0x2 << 2
            if not self.dcs_mclass is None:
                dcs |= 1 << 4
                dcs |= self.dcs_mclass
        else: # not self.dcs_mwi_type is None
            if self.dcs_discard:
                group = 0xC
            else:
                if self.dcs_alphabet == "gsm_default":
                    group = 0xD
                elif self.dcs_alphabet == "utf_16_be":
                    group = 0xE
                else:
                    raise "Invalid alphabet"
            dcs = group << 4
            dcs |= self.dcs_mwi_indication << 3
            dcs |= self.dcs_mwi_type
        return dcs

    def _setDCS( self, dcs ):
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None
        group = ( dcs & 0xF0 ) >> 4
        if 0x0 <= group <= 0x3:
            # general data coding indication
            self.dcs_compressed = bool( dcs & ( 1 << 5 ) )
            if dcs & ( 1 << 4 ):
                # has message class
                self.dcs_mclass = dcs & 0x3
            if (dcs >> 2) & 0x3  == 0x1:
                self.dcs_alphabet = None
            elif (dcs >> 2) & 0x3 == 0x2:
                self.dcs_alphabet = "utf_16_be"
        elif 0x4 <= group <= 0xB:
            # reserved coding groups
            pass
        elif 0xC <= group <= 0xE:
            # MWI groups
            self.dcs_mwi_indication = bool( dcs & 0x8 )
            # dcs & 0x4 (bit 2) is reserved as 0
            self.dcs_mwi_type = [ "voicemail", "fax", "email", "other" ][ dcs & 0x3 ]
            if group == 0xC:
                # discard message
                self.dcs_discard = True
            elif group == 0xD:
                # MWI group: store message (GSM-default)
                pass
            elif group == 0xE:
                # MWI group: store message (USC2)
                self.dcs_alphabet = "utf_16_be"
        elif group == 0xF:
            # data coding/message class
            # dcs & 0x8 (bit 3) is reserved as 0
            if dcs & 0x4:
                self.dcs_alphabet = None
            self.dcs_mclass = dcs & 0x3

    dcs = property( _getDCS, _setDCS )

    def _get_udh( self ):
        map = {}
        # Parse User data headers
        if 0 in self.udh:
            # UDH for concatenated short messages is a list of ID,
            # total number of messages, position of message in csm
            map["csm_id"] = self.udh[0][0]
            map["csm_num"] = self.udh[0][1]
            map["csm_seq"] = self.udh[0][2]
        if 1 in self.udh:
            # Special SMS Message indication
            # WARNING this element could appear multiple times in a message
            map["message-indication-type"] = self.udh[1][0]
            map["message-indication-count"] = self.udh[1][1]
        if 4 in self.udh:
            # Application Port addressing (8-bit)
            map["dst_port"] = self.udh[4][0]
            map["src_port"] = self.udh[4][1]
            map["port_size"] = 8
        if 5 in self.udh:
            # Application Port addressing (16-bit)
            map["dst_port"] = self.udh[5][0]*256 + self.udh[5][1]
            map["src_port"] = self.udh[5][2]*256 + self.udh[5][3]
            map["port_size"] = 16
        if 6 in self.udh:
            # SMSC Control Parameters
            map["smsc-control"] = self.udh[6][0]
        #if 7 in self.udh:
        # UDH Source Indicator
        if 8 in self.udh:
            # Concatenated shor messages (16-bit reference)
            map["csm_id"] = self.udh[0][0]*256 + self.udh[0][1]
            map["csm_num"] = self.udh[0][2]
            map["csm_seq"] = self.udh[0][3]
        #if 9 in self.udh:
            # Wireless Control Message Protocol

        return map

    def _set_udh( self, properties ):
        for k,v in properties.items():
            if k == "csm_id":
                if "csm_num" in properties and "csm_seq" in properties:
                    if v > 255:
                        # Use 16-bit IDs
                        self.udh[8] = [ v/256, v%256, properties["csm_num"], properties["csm_seq"] ]
                    else:
                        self.udh[0] = [ v, properties["csm_num"], properties["csm_seq"] ]
            if k == "message-indication-type":
                if "message-indication-count" in properties:
                    self.udh[1] = [ v, properties["message-indication-count"] ]
            if k == "port_size":
                if "src_port" in properties and "dst_port" in properties:
                    if v == 8:
                        self.udh[4] = [ properties["dst_port"], properties["src_port"] ]
                    elif v == 16:
                        self.udh[5] = [ properties["dst_port"]/256, properties["dst_port"]%256,
                                properties["src_port"]/256, properties["src_port"]%256 ]
            if k == "smsc-control":
                self.udh[6] = v

    def _getProperties( self ):
        map = {}
        map["type"] = self.type

        if len(self.error) > 0:
            map["error"] = self.error

        return map

    def _setProperties( self, properties ):
        pass

    properties = property( _getProperties, _setProperties )

    def _getUdhi( self ):
        return self.udh

    def _setUdhi( self, value ):
        raise "UDHI is readonly"

    udhi = property( _getUdhi, _setUdhi )

    def serviceCenter( self ):
        pass
    def __repr__( self ):
        pass

class SMSDeliver(SMS):

    def parse( self, bytes ):
        """ Decode an sms-deliver message """

        offset = 0

        (self.sca, skip) = self._parse_sca( bytes, offset )
        offset += skip

        # PDU type
        pdu_type = bytes[offset]

        # pdu_mti should already be set by the class
        if self.pdu_mti != pdu_type & 0x03:
            self.error.append("Decoded MTI doesn't match %i != %i" % (self.pdu_mti, pdu_type & 0x03))

        self.pdu_mms = pdu_type & 0x04 != 0
        self.pdu_sri = pdu_type & 0x20 != 0
        self.pdu_udhi = pdu_type & 0x40 != 0
        self.pdu_rp = pdu_type & 0x80 != 0

        offset += 1

        (self.addr, skip) = self._parse_address(bytes, offset)
        offset += skip

        # PID - Protocol identifier
        self.pid = bytes[offset]

        offset += 1
        # DCS - Data Coding Scheme
        self.dcs = bytes[offset]

        offset += 1

        # SCTS - Service Centre Time Stamp
        try:
            self.scts = decodePDUTime( bytes[offset:offset+7] )
        except ValueError, e:
            self.error.append("Service Center Timestamp invalid")

        offset += 7

        # UD - User Data
        ud_len = bytes[offset]
        offset += 1
        self._parse_userdata( ud_len, bytes[offset:] )

    def __init__( self ):
        self.type = "sms-deliver"
        self.sca = False
        self.pdu_mms = True
        self.pdu_rp = False
        self.pdu_udhi = False
        self.pdu_sri = False
        self.udh = {}
        self.ud = ""
        self.pid = 0
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None
        self.scts = (datetime(1980, 01, 01, 00, 00, 00), 0)
        self.error = []

    def _getProperties( self ):
        map = {}
        map.update( SMS._getProperties( self ) )

        map["pid"] = self.pid
        map["more-messages-to-send"] = not self.pdu_mms # This field is backwards!
        map["reply-path"] = self.pdu_rp
        map["status-report-indicator"] = self.pdu_sri
        # XXX Do we want to convey more info here?
        # map["originating-address"]
        map["alphabet"] = SMS_ALPHABET_TO_ENCODING.revlookup(self.dcs_alphabet)

        if map["alphabet"] == "binary":
            map["data"] = self.data

        # FIXME Return correct time with timezoneinfo
        map["timestamp"] = self.scts[0].ctime() + " %+05i" % (self.scts[1]*100)

        map.update( self._get_udh() )

        return map

    def _setProperties( self, properties ):
        self._set_udh( properties )

        for k,v in properties.items():
            if k == "pid":
                self.pid = v
            if k == "more-messages-to-send":
                self.pdu_mms = not v
            if k == "reply-path":
                self.pdu_rp = v
            if k == "status-report-indicator":
                self.pdu_sri = v
            if k == "alphabet":
                self.dcs_alphabet = SMS_ALPHABET_TO_ENCODING[v]
            if k == "data":
                self.data = v
            if k == "timestamp":
                # TODO parse the timestamp correctly
                pass

    properties = property( _getProperties, _setProperties )

    def pdu( self ):
        pdubytes = array('B')

        if self.sca:
            scabcd = self.sca.pdu()
            # SCA has non-standard length
            scabcd[0] = len( scabcd ) - 1
            pdubytes.extend( scabcd )
        else:
            pdubytes.append( 0 )

        pdu_type = self.pdu_mti
        if self.pdu_rp:
            pdu_type += 0x80
        if self.udhi:
            pdu_type += 0x40
        if self.pdu_sri:
            pdu_type += 0x20

        if self.pdu_mms:
            pdu_type += 0x04

        pdubytes.append( pdu_type )

        pdubytes.extend( self.addr.pdu() )

        pdubytes.append( self.pid )

        # We need to check whether we can encode the message with the
        # GSM default charset now, because self.dcs might change
        if not self.dcs_alphabet is None:
            try:
                pduud = self.ud.encode( self.dcs_alphabet )
            except UnicodeError:
                self.dcs_alphabet = "utf_16_be"
                pduud = self.ud.encode( self.dcs_alphabet )
        else:
            # Binary message
            pduud = "".join([ chr(x) for x in self.data ])

        pdubytes.append( self.dcs )

        pdubytes.extend( encodePDUTime( self.scts ) )

        # User data
        if self.udhi:
            pduudh = flatten([ (k, len(v), v) for k,v in self.udh.items() ])
            pduudhlen = len(pduudh)
        else:
            pduudhlen = -1
            padding = 0


        if self.dcs_alphabet == "gsm_default":
            udlen = int( math.ceil( (pduudhlen*8 + 8 + len(pduud)*7)/7.0 ) )
            padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
            pduud = pack_sevenbit( pduud, padding )
        else:
            pduud = map( ord, pduud )
            udlen = len( pduud ) + 1 + pduudhlen

        pdubytes.append( udlen )

        if self.udhi:
            pdubytes.append( pduudhlen )
            pdubytes.extend( pduudh )
        pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )


    def __repr__( self ):
            return """sms-deliver:
Type: %s
ServiceCenter: %s
TimeStamp: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.type, self.sca, self.scts, self.pid, self.dcs, self.addr, self.udh, self.dcs_alphabet, repr(self.ud))

class SMSDeliverReport(SMS):

    def parse( self, bytes, ack=True ):
        """ Decode an sms-deliver-report message """

        # self.ack indicates whether this is sms-deliver-report for RP-ACK or RP-ERROR
        self.ack = ack

        offset = 0

        # PDU type
        pdu_type = bytes[offset]

        # pdu_mti should already be set by the class
        if self.pdu_mti != pdu_type & 0x03:
            self.error.append("Decoded MTI doesn't match %i != %i" % (self.pdu_mti, pdu_type & 0x03))

        self.pdu_udhi = pdu_type & 0x40 != 0

        offset += 1

        if not self.ack:
            self.fcs = bytes[offset]
            offset += 1

        # PI - Parameter Indicator
        pi = bytes[offset]

        self.pdu_pidi = pi & 0x01 != 0
        self.pdu_dcsi = pi & 0x02 != 0
        self.pdu_udli = pi & 0x04 != 0
        offset += 1

        # PID - Protocol identifier
        if self.pdu_pidi:
            self.pid = bytes[offset]
            offset += 1

        # DCS - Data Coding Scheme
        if self.pdu_dcsi:
            self.dcs = bytes[offset]
            offset += 1

        # UD - User Data
        if self.pdu_udli:
            ud_len = bytes[offset]
            offset += 1
            self._parse_userdata( ud_len, bytes[offset:] )

    def __init__( self, ack=True ):
        self.type = "sms-deliver-report"
        self.ack = ack
        self.pdu_udhi = False
        self.pdu_pidi = False
        self.pdu_dcsi = False
        self.pdu_udli = False
        self.udh = {}
        self.ud = ""
        self.pid = 0
        self.fcs = 0xff
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None
        self.error = []

    def _getProperties( self ):
        map = {}
        map.update( SMS._getProperties( self ) )

        if not self.ack:
            map["fcs"] = self.fcs
            if self.fcs in TP_FCS:
                map["failure-cause"] = TP_FCS[self.fcs]

        if self.pdu_pidi:
            map["pid"] = self.pid
        if self.pdu_dcsi:
            map["alphabet"] = SMS_ALPHABET_TO_ENCODING.revlookup(self.dcs_alphabet)

            if map["alphabet"] == "binary":
                map["data"] = self.data

        map.update(self._get_udh())

        return map

    def _setProperties( self, properties ):
        self._set_udh( properties )

        for k,v in properties.items():
            if k == "fcs":
                self.fcs = v
            if k == "pid":
                self.pdu_pidi = True
                self.pid = v
            if k == "alphabet":
                self.pdu_dcsi = True
                self.dcs_alphabet = SMS_ALPHABET_TO_ENCODING[v]
            if k == "data":
                    self.data = v

    properties = property( _getProperties, _setProperties )

    def pdu( self ):
        pdubytes = array('B')

        pdu_type = self.pdu_mti
        if self.udhi:
            pdu_type += 0x40

        pdubytes.append( pdu_type )

        if not self.ack:
            pdubytes.append( self.fcs )

        pi = 0x00
        if self.pdu_pidi:
            pi += 1
        if self.pdu_dcsi:
            pi += 2
        if self.pdu_udli:
            pi += 4

        pdubytes.append( pi )

        pdubytes.extend( encodePDUTime( self.scts ) )

        # XXX Allow the optional fields to be present
        return "".join( [ "%02X" % (i) for i in pdubytes ] )

        if self.pdu_pidi:
            pdubytes.append( self.pid )

        # We need to check whether we can encode the message with the
        # GSM default charset now, because self.dcs might change


        if not self.dcs_alphabet is None:
            try:
                pduud = self.ud.encode( self.dcs_alphabet )
            except UnicodeError:
                self.dcs_alphabet = "utf_16_be"
                pduud = self.ud.encode( self.dcs_alphabet )
        else:
            # Binary message
            pduud = "".join([ chr(x) for x in self.data ])

        pdubytes.append( self.dcs )


        # User data
        if self.udhi:
            pduudh = flatten([ (k, len(v), v) for k,v in self.udh.items() ])
            pduudhlen = len(pduudh)
        else:
            pduudhlen = -1
            padding = 0


        if self.dcs_alphabet == "gsm_default":
            udlen = int( math.ceil( (pduudhlen*8 + 8 + len(pduud)*7)/7.0 ) )
            padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
            pduud = pack_sevenbit( pduud, padding )
        else:
            pduud = map( ord, pduud )
            udlen = len( pduud ) + 1 + pduudhlen

        pdubytes.append( udlen )

        if self.udhi:
            pdubytes.append( pduudhlen )
            pdubytes.extend( pduudh )
        pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )


    def __repr__( self ):
            return """sms-deliver-report:
Type: %s
Timestamp: %s
""" % (self.type, self.scts)

class SMSSubmit(SMS):

    def parse( self, bytes ):
        """ Decode an sms-submit message """

        offset = 0

        (self.sca, skip) = self._parse_sca( bytes, offset )
        offset += skip

        # PDU type
        pdu_type = bytes[offset]

        # pdu_mti should already be set by the class
        if self.pdu_mti != pdu_type & 0x03:
            self.error.append("Decoded MTI doesn't match %i != %i" % (self.pdu_mti, pdu_type & 0x03))

        self.pdu_rd = pdu_type & 0x04 != 0
        self.pdu_vpf =  (pdu_type & 0x18)>>3
        self.pdu_srr = pdu_type & 0x20 != 0
        self.pdu_udhi = pdu_type & 0x40 != 0
        self.pdu_rp = pdu_type & 0x80 != 0

        offset += 1

        # MR - Message Reference
        self.mr = bytes[offset]
        offset += 1

        (self.addr, skip) = self._parse_address( bytes, offset )
        offset += skip

        # PID - Protocol identifier
        self.pid = bytes[offset]

        offset += 1
        # DCS - Data Coding Scheme
        self.dcs = bytes[offset]

        offset += 1

        # VP - Validity Period FIXME
        if self.pdu_vpf == 2:
            # Relative
            self.vp = bytes[offset]
            offset += 1
        elif self.pdu_vpf == 3:
            # Absolute
            try:
                self.vp = decodePDUTime( bytes[offset:offset+7] )
            except ValueError, e:
                self.error.append("Validity Period invalid")
                from datetime import datetime
                self.vp = (datetime(1980, 01, 01, 00, 00, 00), 0)

            offset += 7

        # UD - User Data
        ud_len = bytes[offset]
        offset += 1
        self._parse_userdata( ud_len, bytes[offset:] )

    def __init__( self ):
        self.type = "sms-submit"
        self.sca = False
        self.pdu_rd = False
        self.pdu_vpf = 0
        self.vp = False
        self.pdu_rp = False
        self.pdu_udhi = False
        self.pdu_srr = False
        self.mr = 0
        self.udh = {}
        self.ud = ""
        self.pid = 0
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None
        self.error = []

    def _getProperties( self ):
        map = {}
        map.update( SMS._getProperties( self ) )

        map["reject-duplicates"] = self.pdu_rd
        map["reply-path"] = self.pdu_rp
        map["status-report-request"] = self.pdu_srr
        map["message-reference"] = self.mr
        # XXX Do we want to convey more info here?
        # map["destination-address"]
        map["pid"] = self.pid
        # XXX Validity period and format
        #map["validity-period"] = self.scts[0].ctime() + " %+05i" % (self.scts[1]*100)
        map["alphabet"] = SMS_ALPHABET_TO_ENCODING.revlookup(self.dcs_alphabet)

        if map["alphabet"] == "binary":
            map["data"] = self.data


        map.update(self._get_udh())

        return map

    def _setProperties( self, properties ):
        self._set_udh( properties )

        for k,v in properties.items():
            if k == "reject-duplicates":
                self.pdu_rd = v
            if k == "reply-path":
                self.pdu_rp = v
            if k == "status-report-request":
                self.pdu_srr = v
            if k == "message-reference":
                self.mr = v
            if k == "pid":
                self.pid = v
            if k == "alphabet":
                self.dcs_alphabet = SMS_ALPHABET_TO_ENCODING[v]
            if k == "data":
                    self.data = v

    properties = property( _getProperties, _setProperties )

    def pdu( self ):
        pdubytes = array('B')

        if self.sca:
            scabcd = self.sca.pdu()
            # SCA has non-standard length
            scabcd[0] = len( scabcd ) - 1
            pdubytes.extend( scabcd )
        else:
            pdubytes.append( 0 )

        pdu_type = self.pdu_mti
        if self.pdu_rp:
            pdu_type += 0x80
        if self.udhi:
            pdu_type += 0x40
        if self.pdu_srr:
            pdu_type += 0x20
        if self.pdu_rp:
            pdu_type += 0x04

        pdu_type |= self.pdu_vpf<<3

        # XXX: Allow setting VPF field

        pdubytes.append( pdu_type )

        pdubytes.append( self.mr )

        pdubytes.extend( self.addr.pdu() )

        pdubytes.append( self.pid )

        # We need to check whether we can encode the message with the
        # GSM default charset now, because self.dcs might change
        if not self.dcs_alphabet is None:
            try:
                pduud = self.ud.encode( self.dcs_alphabet )
            except UnicodeError:
                self.dcs_alphabet = "utf_16_be"
                pduud = self.ud.encode( self.dcs_alphabet )
        else:
            # Binary message
            pduud = "".join([ chr(x) for x in self.data ])

        pdubytes.append( self.dcs )

        # VP - Validity Period FIXME
        if self.pdu_vpf == 2:
            # Relative
            pdubytes.append( self.vp )
        elif self.pdu_vpf == 3:
            # Absolute
            pdubytes.extend( encodePDUTime( self.vp ) )

        # User data
        if self.udhi:
            pduudh = flatten([ (k, len(v), v) for k,v in self.udh.items() ])
            pduudhlen = len(pduudh)
        else:
            pduudhlen = -1
            padding = 0


        if self.dcs_alphabet == "gsm_default":
            udlen = int( math.ceil( (pduudhlen*8 + 8 + len(pduud)*7)/7.0 ) )
            padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
            pduud = pack_sevenbit( pduud, padding )
        else:
            pduud = map( ord, pduud )
            udlen = len( pduud ) + 1 + pduudhlen

        pdubytes.append( udlen )

        if self.udhi:
            pdubytes.append( pduudhlen )
            pdubytes.extend( pduudh )
        pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )


    def __repr__( self ):
            return """sms-submit:
Type: %s
ServiceCenter: %s
ValidityPeriod: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.type, self.sca, self.vp, self.pid, self.dcs, self.addr, self.udh, self.dcs_alphabet, repr(self.ud))

class SMSSubmitReport(SMS):

    def parse( self, bytes, ack=True ):
        """ Decode an sms-submit-report message """

        self.ack = ack

        offset = 0

        # PDU type
        pdu_type = bytes[offset]

        # pdu_mti should already be set by the class
        if self.pdu_mti != pdu_type & 0x03:
            self.error.append("Decoded MTI doesn't match %i != %i" % (self.pdu_mti, pdu_type & 0x03))

        # XXX Is 0x04 the correct bit for UDHI? GSM 03.40 says "Bits 7-2 in the TP-MTI are
        # presently unused...", but that leaves only room for the mti field...
        # On page 45 (sms-submit-report for RP-ERROR) it says that Bits 7 and 5-2 are unused
        # which would leave udhi at the same place as in other messages

        self.pdu_udhi = pdu_type & 0x40 != 0

        offset += 1

        if not self.ack:
            self.fcs = bytes[offset]
            offset += 1

        # PI - Parameter Indicator
        pi = bytes[offset]

        self.pdu_pidi = pi & 0x01 != 0
        self.pdu_dcsi = pi & 0x02 != 0
        self.pdu_udli = pi & 0x04 != 0
        offset += 1

        try:
            self.scts = decodePDUTime( bytes[offset:offset+7] )
        except ValueError, e:
            self.error.append("Service Center Time Stamp invalid")

        offset += 7

        # PID - Protocol identifier
        if self.pdu_pidi:
            self.pid = bytes[offset]
            offset += 1

        # DCS - Data Coding Scheme
        if self.pdu_dcsi:
            self.dcs = bytes[offset]
            offset += 1

        # UD - User Data
        if self.pdu_udli:
            ud_len = bytes[offset]
            offset += 1
            self._parse_userdata( ud_len, bytes[offset:] )

    def __init__( self, ack=True ):
        self.ack = ack
        self.type = "sms-submit-report"
        self.scts = False
        self.pdu_udhi = False
        self.pdu_pidi = False
        self.pdu_dcsi = False
        self.pdu_udli = False
        self.udh = {}
        self.ud = ""
        self.fcs = 0xff
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None
        self.scts = (datetime(1980, 01, 01, 00, 00, 00), 0)
        self.error = []

    def _getProperties( self ):
        map = {}
        map.update( SMS._getProperties( self ) )

        map["timestamp"] = self.scts[0].ctime() + " %+05i" % (self.scts[1]*100)
        if not self.ack:
            map["fcs"] = self.fcs
            if self.fcs in TP_FCS:
                map["failure-cause"] = TP_FCS[self.fcs]

        if self.pdu_pidi:
            map["pid"] = self.pid
        if self.pdu_dcsi:
            map["alphabet"] = SMS_ALPHABET_TO_ENCODING.revlookup(self.dcs_alphabet)

            if map["alphabet"] == "binary":
                map["data"] = self.data

        map.update(self._get_udh())

        return map

    def _setProperties( self, properties ):
        self._set_udh( properties )

        for k,v in properties.items():
            if k == "fcs":
                self.fcs = v
            if k == "pid":
                self.pdu_pidi = True
                self.pid = v
            if k == "alphabet":
                self.pdu_dcsi = True
                self.dcs_alphabet = SMS_ALPHABET_TO_ENCODING[v]
            if k == "data":
                    self.data = v

    properties = property( _getProperties, _setProperties )

    def pdu( self ):
        pdubytes = array('B')

        pdu_type = self.pdu_mti
        if self.udhi:
            pdu_type += 0x40

        pdubytes.append( pdu_type )

        if not self.ack:
            pdubytes.append( self.fcs )

        pi = 0x00
        if self.pdu_pidi:
            pi += 1
        if self.pdu_dcsi:
            pi += 2
        if self.pdu_udli:
            pi += 4

        pdubytes.append( pi )

        pdubytes.extend( encodePDUTime( self.scts ) )

        if self.pdu_pidi:
            pdubytes.append( self.pid )

        if self.pdu_dcsi:
            # We need to check whether we can encode the message with the
            # GSM default charset now, because self.dcs might change
            if not self.dcs_alphabet is None:
                try:
                    pduud = self.ud.encode( self.dcs_alphabet )
                except UnicodeError:
                    self.dcs_alphabet = "utf_16_be"
                    pduud = self.ud.encode( self.dcs_alphabet )
            else:
                # Binary message
                pduud = "".join([ chr(x) for x in self.data ])

            pdubytes.append( self.dcs )

        if len(self.ud) > 0:
            # User data
            if self.udhi:
                pduudh = flatten([ (k, len(v), v) for k,v in self.udh.items() ])
                pduudhlen = len(pduudh)
            else:
                pduudhlen = -1
                padding = 0


            if self.dcs_alphabet == "gsm_default":
                udlen = int( math.ceil( (pduudhlen*8 + 8 + len(pduud)*7)/7.0 ) )
                padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
                pduud = pack_sevenbit( pduud, padding )
            else:
                pduud = map( ord, pduud )
                udlen = len( pduud ) + 1 + pduudhlen

            pdubytes.append( udlen )

            if self.udhi:
                pdubytes.append( pduudhlen )
                pdubytes.extend( pduudh )
            pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )

        if self.pdu_pidi:
            pdubytes.append( self.pid )

        # We need to check whether we can encode the message with the
        # GSM default charset now, because self.dcs might change


        if not self.dcs_alphabet is None:
            try:
                pduud = self.ud.encode( self.dcs_alphabet )
            except UnicodeError:
                self.dcs_alphabet = "utf_16_be"
                pduud = self.ud.encode( self.dcs_alphabet )
        else:
            # Binary message
            pduud = "".join([ chr(x) for x in self.data ])

        pdubytes.append( self.dcs )


        # User data
        if self.udhi:
            pduudh = flatten([ (k, len(v), v) for k,v in self.udh.items() ])
            pduudhlen = len(pduudh)
        else:
            pduudhlen = -1
            padding = 0


        if self.dcs_alphabet == "gsm_default":
            udlen = int( math.ceil( (pduudhlen*8 + 8 + len(pduud)*7)/7.0 ) )
            padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
            pduud = pack_sevenbit( pduud, padding )
        else:
            pduud = map( ord, pduud )
            udlen = len( pduud ) + 1 + pduudhlen

        pdubytes.append( udlen )

        if self.udhi:
            pdubytes.append( pduudhlen )
            pdubytes.extend( pduudh )
        pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )


    def __repr__( self ):
            return """sms-submit-report:
Type: %s
Timestamp: %s
""" % (self.type, self.scts)

class SMSStatusReport(SMS):
    pass

class SMSCommand(SMS):
    pass

class CellBroadcast(SMS):
    @classmethod
    def decode( cls, pdu):
        # first convert the string into a bytestream
        bytes = [ int( pdu[i:i+2], 16 ) for i in range(0, len(pdu), 2) ]

        cb = cls()
        cb.sn = bytes[0] << 8 | bytes[1]
        cb.mid = bytes[2] << 8 | bytes[3]
        cb.dcs = bytes[4]
        cb.page = bytes[5]

        userdata = "".join( map( chr, bytes[6:] ) )
        if cb.dcs_alphabet == "gsm_default":
            userdata = unpack_sevenbit(bytes[6:])

        if not cb.dcs_alphabet is None:
            # \n is the padding character in CB messages so strip it
            cb.ud = userdata.decode( cb.dcs_alphabet ).strip("\n")
        else:
            cb.ud = userdata

        return cb

    def __init__(self):
        self.dcs_alphabet = "gsm_default"
        self.dcs_language = None
        self.dcs_language_indication = False
        self.dcs_compressed = False
        self.dcs_mclass = None

    def _getDCS( self ):
        if self.dcs_language_indication is None:
            group = 0x01
            dcs = 0x00
            # FIXME: Why is language ucs2?
            if self.dcs_language == "utf_16_be":
                dcs = 0x01
            dcs = group << 4 | dcs
        else: # not self.dcs_language_indication is None
            if self.dcs_mclass is None:
                if self.dcs_language == "Czech":
                    group = 0x02
                    dcs = 0x00
                else:
                    group = 0x00
                    dcs = CB_PDU_DCS_LANGUAGE.index(self.dcs_language)
            else:
                # General data coding
                group = 0x05
                if self.dcs_compressed:
                    group |= 0x02
                if self.dcs_alphabet is None :
                    dcs |= 0x1 << 2
                elif self.dcs_alphabet == "utf_16_be":
                    dcs |= 0x2 << 2
                dcs |= self.dcs_mclass

            dcs = group << 4 | dcs
        return dcs

    def _setDCS( self, dcs ):
        self.dcs_alphabet = "gsm_default"
        self.dcs_language = None
        self.dcs_language_indication = False
        self.dcs_compressed = False
        self.dcs_mclass = None
        group = ( dcs & 0xF0 ) >> 4
        if group == 0x00:
            # language using the default alphabet
            self.dcs_language = CB_PDU_DCS_LANGUAGE[dcs & 0x0F]
        elif group == 0x01:
            # Message with language indication
            self.dcs_language_indication = True
            if (dcs & 0x0F) == 0x01:
                self.dcs_alphabet = "utf_16_be"
        elif group == 0x02:
            if (dcs & 0x0F) == 0x00:
                self.language = "Czech"
        elif group == 0x03:
            # Reserved
            pass
        elif 0x04 <= group <= 0x07:
            # General data coding
            if (dcs & 0x20):
                self.dcs_compressed = True
            if (dcs & 0x10):
                self.dcs_mclass = (dcs & 0x03)
            if (dcs & 0x0C) >> 2 == 1:
                self.dcs_alphabet = None
            elif (dcs & 0x0C) >> 2 == 2:
                self.dcs_alphabet = "utf_16_be"
        elif 0x08 <= group <= 0x0D:
            # Reserved
            pass
        elif group == 0x0E:
            # WAP specific
            pass
        elif group == 0x0F:
            # data coding/message class
            # dcs & 0x8 (bit 3) is reserved as 0
            if dcs & 0x4:
                self.dcs_alphabet = None
            self.dcs_mclass = dcs & 0x3

    dcs = property( _getDCS, _setDCS )

    def pdu( self ):
        # We don't need to generate the PDU for Cell Broadcasts
        pass

    def __repr__(self):
        return """CellBroadcast
SN: %i
MID: %i
Page: %i
Alphabet: %s
Language: %s
Message: %s""" % (self.sn, self.mid, self.page, self.dcs_alphabet, self.dcs_language, repr(self.ud))

# vim: expandtab shiftwidth=4 tabstop=4
