#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: Parser

"""

#=========================================================================#
class LowlevelAtParser( object ):
    """
    A really simple lowlevel AT response parser.

    Requirements:
    * Support feeding data from the channel in chunks of arbitrary lengths          [ok]
    * Support solicited and unsolicited responses (on the same channel)             [ok]
    * Support single (e.g. +CGMR) and multi requests (+CGMR;+CGMM;+CGMI;+CGSN)      [ok]
    * Handle one-line and multi-line responses                                      [ok]

    Todo:
    * Detect echo mode and adjust itself (or warn)
    * Handle intermediate responses
    * Handle multiline requests
    * Seamless handover to binary mode parsers
    """
#=========================================================================#

    def __init__( self, response, unsolicited ):
        self.response = response
        self.unsolicited = unsolicited

        self.lines = []
        self.curline = ""

    def feed( self, bytes, haveCommand ):
        for b in bytes:
            if b == '\r' or b == '\n':
                if self.curline:
                    if not haveCommand:
                        # FIXME should that be [self.curline] for consistency with solicited responses?
                        self.unsolicited( self.curline )
                        self.curline = ""
                        self.lines = []
                    else:
                        self.lines.append( self.curline )
                        if self.curline == "OK" or self.curline == "ERROR" \
                            or self.curline.startswith( "+CME ERROR" ) \
                            or self.curline.startswith( "+CMS ERROR" ) \
                            or self.curline.startswith( "BUSY" ) \
                            or self.curline.startswith( "CONNECT" ) \
                            or self.curline.startswith( "NO ANSWER" ) \
                            or self.curline.startswith( "NO CARRIER" ) \
                            or self.curline.startswith( "NO DIALTONE" ):
                            self.response( self.lines )
                            self.lines = []
                        self.curline = ""
            else:
                self.curline += b

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    import sys, random, time

    responses = []
    unsoliciteds = []

    def response( chunk ):
        print "response =", repr(chunk)
        responses.append( chunk )

    def unsolicited( chunk ):
        print "unsolicited =", repr(chunk)
        unsoliciteds.append( chunk )

    p = LowlevelAtParser( response, unsolicited )

    random.seed( time.time() )

    # todo use input to read command lines
    while True:
        read = sys.stdin.read( random.randint( 5, 20 ) )
        if read == "":
            break
        else:
            p.feed( read, True )
            time.sleep( 0.01 )

    print repr(p.lines)
    print repr(responses)
    print repr(unsolicited)

