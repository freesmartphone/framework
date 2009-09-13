#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
"""
The Open GSM Daemon - Python Implementation

(C) 2006 Adam Sampson <ats@offog.org>
(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Daniel 'alphaone' Willmann
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: convert

GSM conversion functions.
"""
from datetime import datetime
from const import GSMALPHABET, GSMEXTBYTE, GSMEXTALPHABET, \
    PDUADDR_ENC_TRANS, PDUADDR_DEC_TRANS
from codecs import register, CodecInfo

#=========================================================================#
def flatten(x):
#=========================================================================#
    """flatten(sequence) -> list

    Returns a single, flat list which contains all elements retrieved
    from the sequence and all recursively contained sub-sequences
    (iterables).

    Examples:
    >>> [1, 2, [3,4], (5,6)]
    [1, 2, [3, 4], (5, 6)]
    >>> flatten([[[1,2,3], (42,None)], [4,5], [6], 7, MyVector(8,9,10)])
    [1, 2, 3, 42, None, 4, 5, 6, 7, 8, 9, 10]"""

    result = []
    for el in x:
        #if isinstance(el, (list, tuple)):
        if hasattr(el, "__iter__") and not isinstance(el, basestring):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result

#=========================================================================#
def bcd_decode(bs):
#=========================================================================#
  s = "".join(["%1x%1x" % (b & 0xF, b >> 4) for b in bs])
  if s[-1] == "f":
    s = s[:-1]
  return s

#=========================================================================#
def bcd_encode(number):
#=========================================================================#
    bcd = []
    if type(number) is str:
        # Need to encode with base 16 for the special "digits"
        number = [int(i, 16) for i in number]
    for i in range(0, len(number)-1, 2):
        bcd.append( int(number[i]) | int(number[i+1]) << 4 )
    if len(number)%2 == 1:
        bcd.append( int(number[-1]) | 0x0f << 4 )
    return bcd

#=========================================================================#
def decodePDUTime(bs):
#=========================================================================#
  [year, month, day, hour, minute, second, timezone] = \
                  [((n & 0xf) * 10) + (n >> 4) for n in bs]
  if year >= 90: # I don't know if this is the right cut-off point...
    year += 1900
  else:
    year += 2000

  # Timezone sign bit started out as bit 3 of the nibble-swapped byte. We
  # converted to bcd, so negative timezones are now offset by 10*(1<<3)=80
  if timezone < 80:
    zone = timezone / 4
  else:
    zone = (timezone - 80) / -4.

  # Invalid dates will generate a ValueError here which needs catching in
  # higher levels
  result = datetime(year, month, day, hour, minute, second)

  return ( result, zone )

#=========================================================================#
def encodePDUTime(timeobj):
#=========================================================================#
    td = timeobj[0]
    tzone = timeobj[1]

    year = td.year % 100

    zone = 0
    # Timezone sign bit will go to bit 3 of the nibble-swapped byte. Right
    # now this is an offset of 10*(1<<3)=80
    if tzone < 0:
        zone = 80
        tzone = -tzone

    zone += int(tzone * 4)
    return bcd_encode( [ year/10, year%10, td.month/10, td.month%10,
        td.day/10, td.day%10, td.hour/10, td.hour%10, td.minute/10,
        td.minute%10, td.second/10, td.second%10, zone/10, zone%10 ] )

#=========================================================================#
def gsm_default_encode( input, errors = 'strict' ):
#=========================================================================#
        result = []
        for char in input:
            try:
                result.append( GSMALPHABET.index( char ) )
            except ValueError:
                try:
                    extbyte = GSMEXTALPHABET.index( char )
                    result.append( GSMEXTBYTE )
                    result.append( extbyte )
                except ValueError:
                    raise UnicodeError
                    if errors == 'strict': raise UnicodeError,"invalid SMS character"
                    elif errors == 'replace': result.append(chr(0x3f)) #question mark
                    elif errors == 'ignore': pass
                    else: raise UnicodeError, "unknown error handling"
        return ''.join( map(chr, result) ), len( input )

#=========================================================================#
def gsm_default_decode( input, error = 'strict' ):
#=========================================================================#
        extchar = False
        result = []
        for char in input:
            byte = ord(char)
            if byte == GSMEXTBYTE:
                extchar = True
                continue
            if extchar:
                extchar = False
                try:
                    result += GSMEXTALPHABET[byte]
                except IndexError, e:
                    raise UnicodeError, "character %i unknown in GSM extended plane" % (byte)
            else:
                try:
                    result += GSMALPHABET[byte]
                except IndexError, e:
                    raise UnicodeError, "character %i unknown in GSM basic plane" % (byte)
        return u"".join( result ), len(input)

#=========================================================================#
def gsmcodec(name):
#=========================================================================#
    if name == "gsm_default":
        return CodecInfo( gsm_default_encode, gsm_default_decode, name="gsm_default" )
    elif name == "gsm_ucs2":
        return CodecInfo( UnicodeToucs2hex, ucs2hexToUnicode, name="gsm_ucs2" )

register( gsmcodec )

#=========================================================================#
def unpack_sevenbit( bs, chop = 0 ):
#=========================================================================#
    """Unpack 7-bit characters"""
    result = []
    offset = (7 - chop) % 7
    carry = 0
    for b in bs:
        if not chop:
            result.append( carry | (b & (0xff >> offset + 1)) << offset )
        else:
            chop = 0
        if offset == 6:
            result.append( b >> 1 )
            carry = offset = 0
        else:
            carry = b >> 7 - offset
            offset += 1
    return "".join( map(chr, result) )

#=========================================================================#
def pack_sevenbit( text, crop=0 ):
#=========================================================================#
    """Pack 7-bit characters"""
    bs = [ 0 ] + map( ord, text ) + [ 0 ]
    result = []
    shift = 7 - crop
    for i in range(len(bs)-1):
        if shift == 7:
            shift = 0
            continue

        ch1 = bs[i] & 0x7F
        ch1 = ch1 >> shift
        ch2 = bs[(i+1)] & 0x7F
        ch2 = ch2 << (7-shift)

        result.append( ( ch1 | ch2 ) & 0xFF )

        shift += 1

    return result

#=========================================================================#
def ira_pdu_to_string( pdu ):
#=========================================================================#
    bytes = [ int( pdu[ i:i+2 ], 16 ) for i in range( 0, len(pdu), 2 ) ]
    return unpack_sevenbit( bytes ).strip()

#=========================================================================#
def ucs2hexToUnicode( text, errors="strict" ):
#=========================================================================#
    bytes = []
    for i in range( 0, len(text), 2 ):
        try:
            bytes.append( int( text[i:i+2], 16 ) )
        except ValueError:
            raise UnicodeError
            if errors == 'strict': raise UnicodeError,"invalid PDU Byte"
            elif errors == 'replace': bytes.append(0) # replace with 0
            elif errors == 'ignore': bytes.append(0)
            else: raise UnicodeError, "unknown error handling"
    return "".join( map( chr, bytes ) ).decode("utf_16_be") , len(text)

#=========================================================================#
def UnicodeToucs2hex( text, errors="strict" ):
#=========================================================================#
    bytes = map( ord, text.encode("utf_16_be") )
    return "".join( ( "%02X" % i for i in bytes) ), len(text)

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    assert ira_pdu_to_string( "33DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100" ) == "347745555103", "ira_pdu_to_string failed"
    print "OK"

    assert "00420072006100730069006C002000540065006C00650063006F006D".decode("gsm_ucs2") == "Brasil Telecom", "ucs2hexToUnicode failed"
    print "OK"
