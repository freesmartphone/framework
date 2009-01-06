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
from ogsmd.gsm.const import CB_PDU_DCS_LANGUAGE, TP_MTI_INCOMING, TP_MTI_OUTGOING
import math

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
            number = unpack_sevenbit( number )
            number = number.decode( "gsm_default" )
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
            bytes = [ int( pdu[i:i+2], 16 ) for i in range(0, len(pdu), 2) ]
        except ValueError:
            raise SMSError, "PDU malformed"

        sms = cls( smstype )
        offset = 0

        if sms.type == "sms-deliver" or sms.type == "sms-submit":
            # SCA - Service Center address
            sca_len = bytes[offset]
            offset += 1
            if sca_len > 0:
                sms.sca = PDUAddress.decode( bytes[offset:offset+sca_len] )
            else:
                sms.sca = False
            offset += sca_len

        # PDU type
        pdu_type = bytes[offset]

        sms.pdu_mti = pdu_type & 0x03
        if sms.type == "sms-deliver" or sms.type == "sms-submit":
            sms.pdu_rp = pdu_type & 0x80 != 0
            sms.pdu_udhi = pdu_type & 0x40 != 0
            sms.pdu_srr = pdu_type & 0x20 != 0
            sms.pdu_sri = sms.pdu_srr
            sms.pdu_vpf =  (pdu_type & 0x18)>>3
            sms.pdu_rd = pdu_type & 0x04 != 0
            sms.pdu_mms = sms.pdu_rd
        elif sms.type == "sms-submit-report":
            sms.pdu_udhi = pdu_type & 0x04 != 0

        offset += 1
        if sms.type == "sms-submit":
            # MR - Message Reference
            sms.mr = bytes[offset]
            offset += 1

        # OA/DA - Originating or Destination Address
        # WARNING, the length is coded in digits of the number, not in octets occupied!
        if sms.type == "sms-submit" or sms.type == "sms-deliver":
            oa_len = 1 + (bytes[offset] + 1) / 2
            offset += 1
            sms.oa = PDUAddress.decode( bytes[offset:offset+oa_len] )
            sms.da = sms.oa

            offset += oa_len
            # PID - Protocol identifier
            sms.pid = bytes[offset]

            offset += 1
            # DCS - Data Coding Scheme
            sms.dcs = bytes[offset]

            offset += 1

        if sms.type == "sms-submit-report":
            pi = bytes[offset]
            offset += 1

            sms.pdu_pidi = pi & 0x01 != 0
            sms.pdu_dcsi = pi & 0x02 != 0
            sms.pdu_udli = pi & 0x04 != 0


        if sms.type == "sms-deliver" or sms.type == "sms-submit-report":
            # SCTS - Service Centre Time Stamp
            sms.scts = decodePDUTime( bytes[offset:offset+7] )
            offset += 7
        elif sms.type == "sms-submit":
            # VP - Validity Period FIXME
            if sms.pdu_vpf == 2:
                # Relative
                sms.vp = bytes[offset]
                offset += 1
            elif sms.pdu_vpf == 3:
                # Absolute
                sms.vp = decodePDUTime( bytes[offset:offset+7] )
                offset += 7

        if sms.type == "sms-submit-report" and not sms.pdu_udli:
            return sms

        # UD - User Data
        ud_len = bytes[offset]
        offset += 1
        sms._parse_userdata( ud_len, bytes[offset:] )
        return sms

    def __init__( self, type ):
        self.type = type
        self.sca = False
        self.pdu_udhi = False
        self.pdu_srr = False
        self.pdu_sri = False
        self.pdu_rp = False
        self.pdu_vpf = 0
        self.pdu_rd = False
        self.pdu_mms = False
        self.udh = {}
        self.ud = ""
        self.mr = 0
        self.pid = 0
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = False
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None

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

        # User Data FIXME
        # We need to look at the DCS in order to be able to decide what
        # to use here

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
            self.ud = userdata.decode( self.dcs_alphabet )
        else:
            self.ud = userdata

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

    def _getType( self ):
        return self.mtimap[self.pdu_mti]

    def _setType( self, smstype ):
        if TP_MTI_INCOMING.has_key(smstype):
            self.mtimap = TP_MTI_INCOMING
        elif TP_MTI_OUTGOING.has_key(smstype):
            self.mtimap = TP_MTI_OUTGOING
        else:
            raise "invalid SMS type", smstype

        self.pdu_mti = self.mtimap[smstype]

    type = property( _getType, _setType )

    def _getProperties( self ):
        map = {}
        map["type"] = self.type
        if self.type == "sms-deliver" or self.type == "sms-submit-report":
            # FIXME Return correct time with timezoneinfo
            map["timestamp"] = self.scts[0].ctime() + " %+05i" % (self.scts[1]*100)
        if 0 in self.udh:
            # UDH for concatenated short messages is a list of ID,
            # total number of messages, position of message in csm
            map["csm_id"] = self.udh[0][0]
            map["csm_num"] = self.udh[0][1]
            map["csm_seq"] = self.udh[0][2]
        if 4 in self.udh:
            map["port"] = self.udh[4][0]

        return map

    def _setProperties( self, properties ):
        for k,v in properties.items():
            if k == "csm_id":
                if "csm_num" in properties and "csm_seq" in properties:
                    self.udh[0] = [ v, properties["csm_num"], properties["csm_seq"] ]
            if k == "port":
                self.udh[4] = [v]

    properties = property( _getProperties, _setProperties )

    def _getUdhi( self ):
        return self.udh

    def _setUdhi( self, value ):
        raise "UDHI is readonly"

    udhi = property( _getUdhi, _setUdhi )

    def pdu( self ):
        pdubytes = []
        if self.type == "sms-deliver" or self.type == "sms-submit":
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
        if self.pdu_srr or self.pdu_sri:
            pdu_type += 0x20

        pdu_type += self.pdu_vpf << 3

        if self.pdu_rd or self.pdu_mms:
            pdu_type += 0x04

        pdubytes.append( pdu_type )

        if self.type == "sms-submit":
            pdubytes.append( self.mr )

        if self.type == "sms-deliver" or self.type == "sms-submit":
            pdubytes.extend( self.oa.pdu() )

        if self.type == "sms-deliver" or self.type == "sms-submit":
            pdubytes.append( self.pid )

        if self.type == "sms-deliver" or self.type == "sms-submit":
            # We need to check whether we can encode the message with the
            # GSM default charset now, because self.dcs might change
            if not self.dcs_alphabet is None:
                try:
                    pduud = self.ud.encode( self.dcs_alphabet )
                except UnicodeError:
                    self.dcs_alphabet = "utf_16_be"
                    pduud = self.ud.encode( self.dcs_alphabet )
            else:
                pduud = self.ud

        if self.type == "sms-deliver" or self.type == "sms-submit":
            pdubytes.append( self.dcs )

        if self.type == "sms-submit-report":
            pdubytes.append( 0 )

        if self.type == "sms-deliver" or self.type == "sms-submit-report":
            pdubytes.extend( encodePDUTime( self.scts ) )
        elif self.type == "sms-submit":
            if self.pdu_vpf == 2:
                pdubytes.append( self.vp )
            elif self.pdu_vpf == 3:
                pdubytes.append( encodePDUTime( self.vp ) )

        if self.type == "sms-submit-report" and not self.pdu_udli:
            return "".join( [ "%02X" % (i) for i in pdubytes ] )

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


    def serviceCenter( self ):
        pass
    def __repr__( self ):
        if self.type == "sms-deliver":
            return """SMS:
Type: %s
ServiceCenter: %s
TimeStamp: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.type, self.sca, self.scts, self.pid, self.dcs, self.oa, self.udh, self.dcs_alphabet, repr(self.ud))
        elif self.type == "sms-submit":
            return """SMS:
Type: %s
ServiceCenter: %s
Valid: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.type, self.sca, self.pdu_vpf, self.pid, self.dcs, self.oa, self.udh, self.dcs_alphabet, repr(self.ud))
        elif self.type == "sms-submit-report":
            return """SMS:
Type: %s
TimeStamp: %s
""" % (self.type, self.scts)

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
