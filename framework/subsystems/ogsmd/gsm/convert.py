#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
"""
The Open Device Daemon - Python Implementation

(C) 2006 Adam Sampson <ats@offog.org>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: convert

GSM conversion functions.
"""
from datetime import datetime
from const import GSMALPHABET, GSMEXTBYTE, GSMEXTALPHABET
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
def decodePDUNumber(bs):
#=========================================================================#
    num_type = (bs[0] & 0x70) >> 4
    num_plan = (bs[0] & 0x0F)
    number = bs[1:]
    if number == []:
        number = ""
    elif num_type == 5:
        number = unpack_sevenbit(number)
    else:
        number = bcd_decode(number)
    return (num_type, num_plan, number)

#=========================================================================#
def encodePDUNumber(num):
#=========================================================================#
    if num.type == 5:
        enc = pack_sevenbit(num.number)
        length = len(enc)*2
        if (len(num.number)*7)%8 <= 4:
            length -= 1
    else:
        enc = bcd_encode(num.number)
        length = len(num.number)
    return flatten( [length, 0x80 | num.type << 4 | num.dialplan, enc] )

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
    for i in range(0, len(number)-1, 2):
        bcd.append( int(number[i]) | int(number[i+1]) << 4 )
    if len(number)%2 == 1:
        bcd.append( int(number[-1]) | 0x0f << 4 )
    return bcd

#=========================================================================#
def decodePDUTime(bs):
#=========================================================================#
  bs = [((n & 0xf) * 10) + (n >> 4) for n in bs]
  if bs[0] >= 90: # I don't know if this is the right cut-off point...
    year = 1900 + bs[0]
  else:
    year = 2000 + bs[0]
  timezone = bs[6]
  sign = (timezone >> 7) * 2 - 1
  zone = (timezone & 0x7f) / -4. * sign
  return ( datetime(year, bs[1], bs[2], bs[3], bs[4], bs[5]), zone )

#=========================================================================#
def encodePDUTime(timeobj):
#=========================================================================#
    td = timeobj[0]
    tzone = timeobj[1]

    year = td.year % 100

    zone = 0
    if tzone < 0:
        zone = 0x80
        tzone = -tzone

    zone |= int(tzone * 4)
    return bcd_encode( [ year/10, year%10, td.month/10, td.month%10,
        td.day/10, td.day%10, td.hour/10, td.hour%10, td.minute/10,
        td.minute%10, td.second/10, td.second%10, zone/10, zone%10 ] )

#=========================================================================#
def tobinary( n ):
#=========================================================================#
    s = ""
    for i in range(8):
        s = ("%1d" % (n & 1)) + s
        n >>= 1
    return s

#=========================================================================#
def gsm_default_encode( input, errors = 'strict' ):
#=========================================================================#
        result = []
        for char in input:
            try:
                result.append( GSMALPHABET.index( char ) )
            except KeyError:
                try:
                    extbyte = GSMEXTALPHABET.index( char )
                    result.append( GSMEXTBYTE )
                    result.append( extbyte )
                except KeyError:
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
                result += GSMEXTALPHABET[byte]
            else:
                result += GSMALPHABET[byte]
        return u"".join( result ), len(input)

#=========================================================================#
def gsmcodec(name):
#=========================================================================#
    if name == "gsm_default":
        return CodecInfo( gsm_default_encode, gsm_default_decode, name="gsm_default" )

register( gsmcodec )

#=========================================================================#
def unpack_sevenbit( bs, chop = 0 ):
#=========================================================================#
    """Unpack 7-bit characters"""
    msgbytes = [] + bs
    msgbytes.reverse()
    asbinary = "".join(map(tobinary, msgbytes))
    if chop != 0:
        asbinary = asbinary[:-chop]
    chars = []
    while len(asbinary) >= 7:
        chars.append(int(asbinary[-7:], 2))
        asbinary = asbinary[:-7]
    return "".join( map(chr, chars) )

#=========================================================================#
def pack_sevenbit( text, crop=0 ):
#=========================================================================#
    """Pack 7-bit characters"""
    bytes = map( ord, text )

    bytes.reverse()

    msgbits = []
    msgbytes = []
    for char in bytes:
        bits = []
        for i in range(0, 7):
            bits.append( char%2 )
            char /= 2
        bits.reverse()
        msgbits.extend( bits )

    msgbits.extend( [0]*crop )
    padding = (8 - len(msgbits)%8) % 8
    msgbits = ( [0]* padding ) + msgbits
    while len(msgbits) >= 8:
        byte = 0
        length = min( len(msgbits), 8 )

        for i in range(0,length):
            byte = byte * 2 + msgbits[0]
            msgbits = msgbits[1:]

        msgbytes.append( byte )

    msgbytes.reverse()
    return msgbytes

#=========================================================================#
def ira_pdu_to_string( pdu ):
#=========================================================================#
    bytes = [ int( pdu[ i:i+2 ], 16 ) for i in range( 0, len(pdu), 2 ) ]
    return unpack_sevenbit( bytes ).strip()

#=========================================================================#
def ucs2hexToUnicode( text ):
#=========================================================================#
    bytes = ( int( text[ i:i+2 ], 16 ) for i in range( 0, len(text), 2 ) )
    return "".join( map( chr, bytes ) ).decode("utf_16_be")

#=========================================================================#
def UnicodeToucs2hex( text ):
#=========================================================================#
    bytes = map( ord, text.encode("utf_16_be") )
    return "".join( ( "%02X" % i for i in bytes) )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    assert ira_pdu_to_string( "33DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100" ) == "347745555103", "ira_pdu_to_string failed"
    print "OK"

    assert ucs2hexToUnicode( "00420072006100730069006C002000540065006C00650063006F006D" ) == "Brasil Telecom", "ucs2hexToUnicode failed"
    print "OK"
