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

#=========================================================================#
def decodePDUNumber(bs):
#=========================================================================#
    num_type = (bs[0] & 0x70) >> 4
    num_plan = (bs[0] & 0x0F)
    number = bs[1:]
    if num_type == 5:
        # FIXME: 8 seems to be right here, how to calculate?
        pad = 8
        number = unpack_sevenbit(bs, pad)
    else:
        number = bcd_decode(bs)
    return (num_type, num_plan, number)

#=========================================================================#
def bcd_decode(bs):
#=========================================================================#
  s = "".join(["%1x%1x" % (b & 0xF, b >> 4) for b in bs])
  if s[-1] == "f":
    s = s[:-1]
  return s

#=========================================================================#
def decodePDUTime(bs):
#=========================================================================#
  bs = [((n & 0xf) * 10) + (n >> 4) for n in bs]
  if bs[0] >= 90: # I don't know if this is the right cut-off point...
    year = 1900 + bs[0]
  else:
    year = 2000 + bs[0]
  timezone = bs[6]
  sign = (timezone >> 7) * -2 + 1
  zone = (timezone & 0x7f) / -4. * sign
  return ( datetime(year, bs[1], bs[2], bs[3], bs[4], bs[5]), zone )

#=========================================================================#
def tobinary( n ):
#=========================================================================#
    s = ""
    for i in range(8):
        s = ("%1d" % (n & 1)) + s
        n >>= 1
    return s

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
    return "".join(map(chr, chars))

#=========================================================================#
def ira_pdu_to_string( pdu ):
#=========================================================================#
    bytes = [ int( pdu[ i:i+2 ], 16 ) for i in range( 0, len(pdu), 2 ) ]
    return unpack_sevenbit( bytes ).strip()

#=========================================================================#
def ucs2_hex_to_string( text ):
#=========================================================================#
    bytes = ( int( text[ i:i+4 ], 16 ) for i in range( 0, len(text), 4 ) )
    return "".join( ( chr(i) for i in bytes ) )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    assert ira_pdu_to_string( "33DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100" ) == "347745555103", "ira_pdu_to_string failed"
    print "OK"

    assert ucs2_hex_to_string( "00420072006100730069006C002000540065006C00650063006F006D" ) == "Brasil Telecom", "ucs2_hex_to_string failed"
    print "OK"
