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
import math

#    ** Dekodieren
#    smsobject = decodeSMS( pdu )
#    print "von", smsobject.sender(), "um", smsobject.arrivalTime(), "via" smsobject.serviceCenter(), ...
#    print "uses charset", smsobject.charset(), ...
#    ** Enkodieren
#    smsobject = encodeSMS( peer, sender, serviceCenter )
#    pdu = smsobject.pdu()
# * AbstractSms (uebernimmt codierung/decodierung)
# * SmsMessagePart (repraesentiert eine SMS "on the wire")
# * SmsMessage (repraesentiert eine -- moeglicherweise Multipart -- Nachricht)
# * Weitere, fuer spezifische SMS-Typen (Status Report) eigene Klassen? Ggfs. zu komplex.

def decodeSMS( pdu, direction ):
    # first convert the string into a bytestream
    bytes = [ int( pdu[i:i+2], 16 ) for i in range(0, len(pdu), 2) ]

    sms = AbstractSMS( direction )

    offset = 0
    # SCA - Service Center address
    sca_len = bytes[offset]
    offset += 1
    if sca_len > 0:
        sms.sca = PDUAddress( *decodePDUNumber( bytes[offset:offset+sca_len] ) )
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
    sms.oa = PDUAddress( *decodePDUNumber( bytes[offset:offset+oa_len] ) )
    sms.da = sms.oa

    offset += oa_len
    # PID - Protocol identifier
    sms.pid = bytes[offset]

    offset += 1
    # DCS - Data Coding Scheme FIXME
    sms.dcs = bytes[offset]
    sms._parseDCS( sms.dcs )

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
    parse_userdata( sms, ud_len, bytes[offset:] )
    return sms

def parse_userdata( sms, ud_len, bytes ):
    offset = 0
    sms.udh = []
    if sms.pdu_udhi:
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
            sms.udh.append( (iei, ie_data) )

    # User Data FIXME
    # We need to look at the DCS in order to be able to decide what
    # to use here

    # We need to lose the padding bits before the start of the
    # seven-bit packed data, which means we need to figure out how
    # many there are...
    # See the diagram on page 58 of GSM_03.40_6.0.0.pdf.

    userdata = "".join( map( chr, bytes[offset:] ) )
    if sms.dcs_alphabet == "gsm_default":
        padding_size = ((7 * ud_len) - (8 * (offset))) % 7
        userdata = unpack_sevenbit(bytes[offset:], padding_size)

    if not sms.dcs_alphabet is None:
        sms.ud = userdata.decode( sms.dcs_alphabet )

class PDUAddress:
    def __init__( self, type, dialplan, number ):
        self.type = type
        self.dialplan = dialplan
        self.number = number
    def __str__( self ):
        prefix = ""
        if self.type == 1:
            prefix = "+"
        return prefix + self.number

class AbstractSMS:
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
        self.mr = 0
        self.pid = 0
        self.dcs = 0
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = None
        self.dcs_discard = False
        self.dcs_mwi_indication = None
        self.dcs_mwi_type = None
        self.dcs_mclass = None

    def _parseDCS( self, dcs ):
        self.dcs_alphabet = "gsm_default"
        self.dcs_compressed = None
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
                self.alphabet = "utf_16_be"
        elif group == 0xF:
            # data coding/message class
            # dcs & 0x8 (bit 3) is reserved as 0
            if dcs & 0x4:
                self.alphabet = None
            self.dcs_mclass = dcs & 0x3
    def pdu( self ):
        pdubytes = []
        if self.sca:
            scabcd = bcd_encode( self.sca.number )
            pdubytes.append( len(scabcd) + 1 )
            pdubytes.append( 0x80 | (self.sca.type << 4) | self.sca.dialplan )
            pdubytes.extend( scabcd )
            # FIXME This won't work with alphanumeric "numbers"
        else:
            pdubytes.append( 0 )

        pdu_type = self.pdu_mti
        if self.pdu_rp:
            pdu_type += 0x80
        if self.pdu_udhi:
            pdu_type += 0x40
        if self.pdu_srr or self.pdu_sri:
            pdu_type += 0x20

        pdu_type += self.pdu_vpf << 3

        if self.pdu_rd or self.pdu_mms:
            pdu_type += 0x04

        pdubytes.append( pdu_type )

        if self.pdu_mti == 1:
            pdubytes.append( self.mr )

        pdubytes.extend( encodePDUNumber(self.oa) )

        pdubytes.append( self.pid )
        pdubytes.append( self.dcs )

        if self.pdu_mti == 0:
            pdubytes.extend( encodePDUTime( self.scts ) )
        else:
            if self.pdu_vpf == 2:
                pdubytes.append( self.vp )
            elif self.pdu_vpf == 3:
                pdubytes.append( encodePDUTime( self.vp ) )

        # User data

        if self.pdu_udhi:
            pduudh = flatten([ (header[0], len(header[1]), header[1]) for header in self.udh ])
            pduudhlen = len(pduudh)
        else:
            pduudhlen = -1
            padding = 0


        if not self.dcs_alphabet is None:
            pduud = self.ud.encode( self.dcs_alphabet )
        else:
            pduud = self.ud

        if self.dcs_alphabet == "gsm_default":
            udlen = int( math.ceil( (pduudhlen*8 + 8 + len(self.ud)*7)/7.0 ) )
            padding = (7 * udlen - (8 + 8 * (pduudhlen))) % 7
            pduud = pack_sevenbit( pduud, padding )
        else:
            pduud = map( ord, pduud )
            udlen = len( pduud ) + 1 + pduudhlen

        pdubytes.append( udlen )

        if self.pdu_udhi:
            pdubytes.append( pduudhlen )
            pdubytes.extend( pduudh )
        pdubytes.extend( pduud )

        return "".join( [ "%02X" % (i) for i in pdubytes ] )


    def serviceCenter( self ):
        pass
    def repr( self ):
        if self.pdu_mti == 0:
            return """AbstractSMS:
ServiceCenter: %s
TimeStamp: %s
PID: %i
DCS: 0x%x
Number: %s
Headers: %s
Message: %s
""" % (self.sca, self.scts, self.pid, self.dcs, self.oa, self.udh, self.ud)
        else:
            return """AbstractSMS:
ServiceCenter: %s
Valid: %s
PID: %i
DCS: 0x%x
Number: %s
Headers: %s
Message: %s
""" % (self.sca, self.pdu_vpf, self.pid, self.dcs, self.oa, self.udh, self.ud)

if __name__ == "__main__":
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
    "0791447758100650040DD0F334FC1CA6970100008080312170224008D4F29CDE0EA7D9"
    ]
    pdus_MO = [
    "07910447946400F011000A9270042079330000AA0161"
    ]

    def testpdu(pdu, dir):
        sms = decodeSMS(pdu, dir)
        genpdu = sms.pdu()
        if pdu != genpdu:
            print "ERROR: Reencoded SMS doesn't match"
            print "Orig PDU: ", pdu
            print "ReencPDU: ", genpdu
            print sms.repr()
            sms = decodeSMS(genpdu, dir)
        print sms.repr()

    for pdu in pdus_MT:
        testpdu(pdu, "MT")
    for pdu in pdus_MO:
        testpdu(pdu, "MO")

# vim: expandtab shiftwidth=4 tabstop=4
