#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: parser

"""

#=========================================================================#
class SimpleLowlevelAtParser( object ):
#=========================================================================#
    """
    A really simple lowlevel AT response parser.

    Requirements:
    * Support feeding data from the channel in chunks of arbitrary lengths          [ok]
    * Support solicited and unsolicited responses (on the same channel)             [ok]
    * Support single (e.g. +CGMR) and multi requests (+CGMR;+CGMM;+CGMI;+CGSN)      [ok]
    * Handle one-line and multi-line responses                                      [ok]
    * Handle multiline requests by supporting continuation '\r\n> '                 [ok, but see NOTE]

    Todo:
    * Detect echo mode and adjust itself (or warn)
    * Handle intermediate responses
    * Handle multiline answers with empty lines (e.g. SMS)
    * Handle multiline unsolicited responses (e.g. +CBM)
    * Seamless handover to binary mode parsers
    """

    def __init__( self, response, unsolicited ):
        self.response = response
        self.unsolicited = unsolicited

        self.lines = []
        self.curline = ""

    def feed( self, bytes, haveCommand ):
        # NOTE: the continuation query relies on '\r\n> ' not being
        # fragmented... question: is that always correct? If not,
        # we better keep the state. We could also enhance the signature
        # to support handing a haveContinuation parameter over to here.
        if bytes == "\r\n> ":
            self.response( [] )
            self.lines = []
            self.curline = ""
            return
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
                        if self.curline == "OK" \
                            or self.curline == "ERROR" \
                            or self.curline.startswith( "+CME ERROR" ) \
                            or self.curline.startswith( "+CMS ERROR" ) \
                            or self.curline.startswith( "+EXT ERROR" ) \
                            or self.curline.startswith( "BUSY" ) \
                            or self.curline.startswith( "CONNECT" ) \
                            or self.curline.startswith( "NO ANSWER" ) \
                            or self.curline.startswith( "NO CARRIER" ) \
                            or self.curline.startswith( "NO DIALTONE" ):
                            self.response( self.lines )
                            self.lines = []
                        self.curline = ""
            else:
                # yes, this is slow. We're going to profile and optimize, once it's stable...
                self.curline += b

#=========================================================================#
class StateBasedLowlevelAtParser( object ):
#=========================================================================#
    """
    A really simple lowlevel AT response parser.

    Requirements:
    * Support feeding data from the channel in chunks of arbitrary lengths          [ok]
    * Support solicited and unsolicited responses (on the same channel)             [ok]
    * Support single (e.g. +CGMR) and multi requests (+CGMR;+CGMM;+CGMI;+CGSN)      [ok]
    * Handle one-line and multi-line responses                                      [ok]
    * Handle multiline requests by supporting continuation '\r\n> '                 [ok, but see NOTE]

    Todo:
    * Detect echo mode and adjust itself (or warn)
    * Handle intermediate responses
    * Handle multiline answers with empty lines (e.g. SMS)
    * Handle multiline unsolicited responses (e.g. +CBM)
    * Seamless handover to binary mode parsers
    """

    def __init__( self, response, unsolicited ):
        self.response = response
        self.unsolicited = unsolicited
        self.state = self.reset()

    def reset( self ):
        self.lines = []
        self.curline = ""
        return self.state_start

    def feed( self, bytes, haveCommand ):
        # NOTE: the continuation query relies on '\r\n> ' not being
        # fragmented... question: is that always correct? If not,
        # we better keep the state. We could also enhance the signature
        # to support handing a haveContinuation parameter over to here.

        if bytes == "\r\n> ":
            self.response( [] )
            self.state = self.reset()
            return

        for b in bytes:
            print "PARSER DEBUG: [%s] feeding %s to %s" % ( ( "solicited" if haveCommand else "unsolicited" ), repr(b), self.state )

            nextstate = self.state( b, haveCommand )
            if nextstate is None:
                print "PARSER DEBUG: WARNING: UNDEFINED PARSER STATE! trying to recover..."
            else:
                self.state = nextstate

    def state_start( self, b, s ):
        if b == '\r':
            return self.state_start_r

    def state_start_r( self, b, s ):
        if b == '\n':
            return self.state_inline

    def state_inline( self, b, s ):
        if b not in "\r\n":
            self.curline += b
            return self.state_inline
        else:
            if b == "\r":
                return self.state_inline_r

    def state_inline_r( self, b, s ):
        if b == '\r':
            return self.state_inline_multipleR
        if b == '\n':
            if s:
                return self.solicitedLineCompleted()
            else:
                return self.unsolicitedLineCompleted()

    def state_inline_multipleR( self, b, s ):
        if b == '\r':
            return self.state_inline_multipleR
        if b == '\n':
            if s:
                return self.solicitedLineCompleted( True )
            else:
                return self.unsolicitedLineCompleted( True )

    def state_postcommand( self, b, s ):
        if b == '\r':
            return self.state_postcommand_r

    def state_postcommand_r( self, b, s ):
        if b == '\n':
            return self.reset()

    def solicitedLineCompleted( self, multipleR = False ):
        print "PARSER DEBUG: solicited line completed, line=", repr(self.curline), "previous lines=", self.lines
        if self.curline:
            self.lines.append( self.curline )
            # check for termination
            if self.curline == "OK" \
            or self.curline == "ERROR" \
            or self.curline.startswith( "+CME ERROR" ) \
            or self.curline.startswith( "+CMS ERROR" ) \
            or self.curline.startswith( "+EXT ERROR" ) \
            or self.curline.startswith( "BUSY" ) \
            or self.curline.startswith( "CONNECT" ) \
            or self.curline.startswith( "NO ANSWER" ) \
            or self.curline.startswith( "NO CARRIER" ) \
            or self.curline.startswith( "NO DIALTONE" ):
                print "PARSER DEBUG: solicited response completed"
                self.response( self.lines )
                return self.reset()
            else:
                self.curline = ""
                return self.state_inline
        else:
            print "PARSER WARNING: empty line within solicited response. Ignoring."
            self.curline = ""
            return self.state_inline

    def unsolicitedLineCompleted( self, multipleR = False ):
        print "PARSER DEBUG: unsolicited line completed"
        if self.curline:
            self.lines.append( self.curline )
            self.unsolicited( self.lines )
            return self.reset()

#
# Choose parser and cleanup namespace
#
USE_EXPERIMENTAL_PARSER = False

if USE_EXPERIMENTAL_PARSER:
    LowlevelAtParser = StateBasedLowlevelAtParser
else:
    LowlevelAtParser = SimpleLowlevelAtParser
del SimpleLowlevelAtParser
del StateBasedLowlevelAtParser

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

