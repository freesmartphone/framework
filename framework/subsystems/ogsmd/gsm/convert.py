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
if __name__ == "__main__":
#=========================================================================#
    assert ira_pdu_to_string( "33DAED46ABD56AB5186CD668341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D168341A8D46A3D100" ) == "347745555103", "ira_pdu_to_string conversion failed"
    print "OK"
