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
from ogsmd.gsm.const import CB_PDU_DCS_LANGUAGE
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
    def decode( cls, pdu, direction ):
        # first convert the string into a bytestream
        try:
            bytes = [ int( pdu[i:i+2], 16 ) for i in range(0, len(pdu), 2) ]
        except ValueError:
            raise SMSError, "PDU malformed"

        sms = cls( direction )

        offset = 0
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
        sms.pdu_rp = pdu_type & 0x80 != 0
        sms.pdu_udhi = pdu_type & 0x40 != 0
        sms.pdu_srr = pdu_type & 0x20 != 0
        sms.pdu_sri = sms.pdu_srr
        sms.pdu_vpf =  (pdu_type & 0x18)>>3
        sms.pdu_rd = pdu_type & 0x04 != 0
        sms.pdu_mms = sms.pdu_rd

        offset += 1
        if sms.pdu_mti == 1:
            # MR - Message Reference
            sms.mr = bytes[offset]
            offset += 1

        # OA/DA - Originating or Destination Address
        # WARNING, the length is coded in digits of the number, not in octets occupied!
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
        if sms.pdu_mti == 0:
            # SCTS - Service Centre Time Stamp
            sms.scts = decodePDUTime( bytes[offset:offset+7] )
            offset += 7
        else:
            # VP - Validity Period FIXME
            if sms.pdu_vpf == 2:
                # Relative
                sms.vp = bytes[offset]
                offset += 1
            elif sms.pdu_vpf == 3:
                # Absolute
                sms.vp = decodePDUTime( bytes[offset:offset+7] )
                offset += 7

        # UD - User Data
        ud_len = bytes[offset]
        offset += 1
        sms._parse_userdata( ud_len, bytes[offset:] )
        return sms

    def __init__( self, direction ):
        self.direction = direction
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
        if self.direction == "MT":
            map = TP_MTI_INCOMING
        elif self.direction == "MO":
            map = TP_MTI_OUTGOING
        return map[self.pdu_mti]

    def _setType( self, smstype ):
        if TP_MTI_INCOMING.has_key(smstype):
            self.direction = "MT"
            self.pdu_mti = TP_MTI_INCOMING[smstype]
        elif TP_MTI_OUTGOING.has_key(smstype):
            self.direction = "MO"
            self.pdu_mti = TP_MTI_OUTGOING[smstype]

    type = property( _getType, _setType )

    def _getProperties( self ):
        map = {}
        map["type"] = self.type
        if self.type == "sms-deliver":
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

        if self.pdu_mti == 1:
            pdubytes.append( self.mr )

        pdubytes.extend( self.oa.pdu() )

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
            pduud = self.ud

        pdubytes.append( self.dcs )

        if self.pdu_mti == 0:
            pdubytes.extend( encodePDUTime( self.scts ) )
        else:
            if self.pdu_vpf == 2:
                pdubytes.append( self.vp )
            elif self.pdu_vpf == 3:
                pdubytes.append( encodePDUTime( self.vp ) )

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
        if self.pdu_mti == 0:
            return """MT SMS:
ServiceCenter: %s
TimeStamp: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.sca, self.scts, self.pid, self.dcs, self.oa, self.udh, self.dcs_alphabet, repr(self.ud))
        else:
            return """MO SMS:
ServiceCenter: %s
Valid: %s
PID: 0x%x
DCS: 0x%x
Number: %s
Headers: %s
Alphabet: %s
Message: %s
""" % (self.sca, self.pdu_vpf, self.pid, self.dcs, self.oa, self.udh, self.dcs_alphabet, repr(self.ud))

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

if __name__ == "__main__":
    import sys
    #============================================================================#
    def readFromFile( path ):
    #============================================================================#
        try:
            value = open( path, 'r' ).read().strip()
        except IOError, e:
            print( "(could not read from '%s': %s)" % ( path, e ) )
            return "N/A"
        else:
            return value

    pdus_MT = [
    "0791448720900253040C914497035290960000500151614414400DD4F29C9E769F41E17338ED06",
    "0791448720003023440C91449703529096000050015132532240A00500037A020190E9339A9D3EA3E920FA1B1466B341E472193E079DD3EE73D85DA7EB41E7B41C1407C1CBF43228CC26E3416137390F3AABCFEAB3FAAC3EABCFEAB3FAAC3EABCFEAB3FAAC3EABCFEAB3FADC3EB7CFED73FBDC3EBF5D4416D9457411596457137D87B7E16438194E86BBCF6D16D9055D429548A28BE822BA882E6370196C2A8950E291E822BA88",
    "0791448720003023440C91449703529096000050015132537240310500037A02025C4417D1D52422894EE5B17824BA8EC423F1483C129BC725315464118FCDE011247C4A8B44",
    "07914477790706520414D06176198F0EE361F2321900005001610013334014C324350B9287D12079180D92A3416134480E",
    "0791448720003023440C91449703529096000050016121855140A005000301060190F5F31C447F83C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D2064FD3C07D1DF2072B90C9FBB40C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E8",
    "0791448720003023440C91449703529096000050016121850240A0050003010602DE2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E1731708593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41",
    "0791448720003023440C91449703529096000050016121854240A0050003010603C8E5327CEE0221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E10B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E1",
    "0791448720003023400C91449703529096000050016121858240A0050003010604E62E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC0542D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE028140C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D",
    "0791448720003023400C91449703529096000050016121853340A005000301060540C8FA790EA2BF41E472193E7781402064FD3C07D1DF2072B90C9FBB402010B27E9E83E86F10B95C86CF5D201008593FCF41F437885C2EC3E72E100884AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B84AC9FE720FA1B442E97E17317080442D6CF7310FD0D2297CBF0B90B040221EBE73988FE0691CB65F8DC05028190",
    "0791448720003023440C914497035290960000500161218563402A050003010606EAE73988FE0691CB65F8DC05028190F5F31C447F83C8E5327CEE0281402010",
    "07918167830071F1040BD0C7F7FBCC2E030000808010800120804AD0473BED2697D9F3B20E644CCBDBE136835C6681CCF2B20B147381C2F5B30B04C3E96630500B1483E96030501A34CDB7C5E9B71B847AB2CB2062987D0E87E5E414",
    "07918167830071F1040BD0C7F7FBCC2E0300008080203200748078D0473BED2697D9F3B20E442DCFE9A076793E0F9FCBA07B9A8E0691C3EEF41C0D1AA3C3F2F0985E96CF75A00EE301E22C1C2C109B217781642E50B87E76816433DD0C066A81E60CB70B347381C2F5B30B",
    "0791447758100650040C9194714373238200008080312160304019D4F29C0E6A97E7F3F0B90CB2A7C3A0791A7E0ED3CB2E",
    "0791447758100650040DD0F334FC1CA6970100008080312170224008D4F29CDE0EA7D9",
    "0791889653704434040C9188969366423600008090017134632302CA34",
    "0791889663000009040C918896631009910008809061510540238453485B89FF0167094EF681C97D055FC38DF376844E8B548C4F608AAA54E6FF016709500B59735B69525B52A0516590FD6703753759738AAA60F389818A8D8B584F60FF0C624B6A5F5FEB64A500350032003163090033628A63E16A5F67038A8D8B5859793002621664A50035003200316309003251FA73FE611B60C5597D904B5146FF01",
    "0791889663000019040C918896631030990008809071619483234E60A86709672A63A54F8696FB003A000A00300039002F00310037002000300034003A003400330050004D4F8681EA0030003900380038003500360033003900390036002000280032901A0029000A",
    "0791889663000009040C918896631009910008809071717374238A7E415FD951B76DE1768457CE5E02FF0C4F609858610F548C6211505A670B53CB55CEFF1F624B6A5F76F464A500350032003163090031518D630900338F3851650033003200320030003000390033621167037B495F854F60771F5FC376844F8696FB007E621664A5003500320031630900328AC75FC3804A59298DA330014EA453CB8D855BB96613007E",
    "0791889663000009040C91889671342752000080908171153223282073788E4EBFDD2B1CCE96C3E16AB6592E67D32944ECF7780D9A8FE5E5B25BA468B514",
    "0791889663000019040C918896138188020008809091907405238050B38A0A606F003F767E842C734E91D190017D664F6076846D3B52D590FD958B8DD15169500B67084E86FF0C4F605831540D4E8655CEFF0173FE572853EA898150B34E00500B7A7A767D7C218A0A52300030003900330031002D003100380031003900330030514D8CBB5831540DFF0C6A5F67035C31662F4F6076845594FF01",
    "07918896532430280406918816880000809042215024235FC3309B0D42BEDB6590380F22A7C3ECB4FB0CE2AD7C20DEF85D77D3E579D0F84D2E836839900FC403C1D16F7719E47E837CA01D681866B341ECF738CC06A9EB733A889C0EB341ECF738CC06C1D16F7719E47EBB00",
    "07914140279505F74404D011002000800190819234000704010200018000",
    "07914140279505F74404D011002000800190913285000704010200028000",
    "07914140279505F74404D011002000800190320243000704010200038000",
    "0791947106004034040C9194713900303341008011311265854059D6B75B076A86D36CF11BEF024DD365103A2C2EBB413390BB5C2F839CE1315A9E1EA3E96537C805D2D6DBA0A0585E3797DDA0FB1ECD2EBB41D37419244ED3E965906845CBC56EB9190C069BCD6622",
    "0791947106004034040C9194713900303341008011312270804059D6B75B076A86D36CF11BEF024DD365103A2C2EBB413490BB5C2F839CE1315A9E1EA3E96537C805D2D6DBA0A0585E3797DDA0FB1ECD2EBB41D37419244ED3E965906845CBC56EB9190C069BCD6622",

    ]

    pdus_MO = [
    "07910447946400F011000A9270042079330000AA0161",
    "079194710716000001310C919491103246570000061B1EBD3CA703",
    ]

    pdus_ACKPDU = [
    "010080110191146140",
    "010080112102618040",
    ]

    pdus_CB = [
    "001000DD001133DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100",
    ]

    if len(sys.argv) == 3:
        pdus_MT = readFromFile(sys.argv[1]).split("\n")
        pdus_MO = readFromFile(sys.argv[2]).split("\n")


    def testpdu(pdu, dir):
        try:
            sms = SMS.decode(pdu, dir)
            genpdu = sms.pdu()
            if pdu != genpdu:
                print "ERROR: Reencoded SMS doesn't match"
                print "Orig PDU: ", pdu
                print "ReencPDU: ", genpdu
                print repr(sms)
                sms = SMS.decode(genpdu, dir)
            print repr(sms)
        except SMSError, e:
            print "%s, PDU was: %s\n" % (e, pdu)

    for pdu in pdus_MT:
        testpdu(pdu, "MT")

    for pdu in pdus_MO:
        testpdu(pdu, "MO")

    for pdu in pdus_CB:
        cb = CellBroadcast.decode(pdu)
        print repr(cb)

# vim: expandtab shiftwidth=4 tabstop=4
