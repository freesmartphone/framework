#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: parser

"""

DEBUG = False

#=========================================================================#
class StateBasedLowlevelAtParser( object ):
#=========================================================================#
    """
    A state machine based lowlevel AT response parser.

    Requirements:
    * Support feeding data from the channel in chunks of arbitrary lengths          [ok]
    * Support solicited and unsolicited responses (on the same channel)             [ok]
    * Support single (e.g. +CGMR) and multi requests (+CGMR;+CGMM;+CGMI;+CGSN)      [ok]
    * Handle one-line and multi-line responses                                      [ok]
    * Handle multiline unsolicited responses (e.g. +CBM)                            [ok, but kind of ugly]
    * Handle multiline requests by supporting continuation '\r\n> '                 [ok, but see NOTE]

    Todo:
    * Detect echo mode and adjust itself (or warn)
    * Handle multiline answers with empty lines (e.g. in SMS)
    * Seamless handover to binary mode parsers / data connections
    """

    def __init__( self, response, unsolicited ):
        self.response = response
        self.unsolicited = unsolicited
        self.state = self.reset()

    def reset( self ):
        self.lines = []
        self.curline = ""
        self.hasPdu = False
        return self.state_start

    def feed( self, bytes, haveCommand ):
        # NOTE: the continuation query relies on '\r\n> ' not being
        # fragmented... question: is that always correct? If not,
        # we better keep the state. We could also enhance the signature
        # to support handing a haveContinuation parameter over to here.

        if bytes == "\r\n> ":
            if DEBUG: print "PARSER DEBUG: got continuation character. sending empty response"
            self.response( [] )
            self.state = self.reset()
            return

        for b in bytes:
            if DEBUG: print "PARSER DEBUG: [%s] feeding %s to %s" % ( ( "solicited" if haveCommand else "unsolicited" ), repr(b), self.state )

            nextstate = self.state( b, haveCommand )
            if nextstate is None:
                print "PARSER DEBUG: WARNING: UNDEFINED PARSER STATE!"
                print "previous bytes were:", repr(bytes)
                print "current byte is:", repr(b)
                print "lines:", repr(self.lines)
                print "curline:", repr(self.curline)
                print "solicited:", haveCommand
                self.state = self.reset()
                break
            else:
                self.state = nextstate

    def state_start( self, b, s ):
        if b == '\r':
            return self.state_start_r
        # this is unusal, but we are forgiving
        if b == '\n':
            return self.state_inline
        # this is even more unusual, but we are _really_ forgiving
        return self.state_inline( b, s )

    def state_start_r( self, b, s ):
        if b == '\n':
            return self.state_inline

    def state_inline( self, b, s ):
        # FIXME checking the number of " in self.curline violates
        # the state machine layer and slows down the parser.
        # We better map this to the state machine instead.
        if b not in "\r\n" or self.curline.count('"')%2:
            self.curline += b
            return self.state_inline
        else:
            if b == "\r":
                return self.state_inline_r
            # usually this should not happen, but some SMS are badly formatted
            if b == '\n':
                if s:
                    return self.solicitedLineCompleted()
                else:
                    return self.unsolicitedLineCompleted()

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

    def solicitedLineCompleted( self, multipleR = False ):
        if DEBUG: print "PARSER DEBUG: solicited line completed, line=", repr(self.curline), "previous lines=", self.lines
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
                if DEBUG: print "PARSER DEBUG: solicited response completed"
                self.response( self.lines )
                return self.reset()
            else:
                self.curline = ""
                return self.state_inline
        else:
            if DEBUG: print "PARSER WARNING: empty line within solicited response. Ignoring."
            self.curline = ""
            return self.state_inline

    def unsolicitedLineCompleted( self, multipleR = False ):
        if DEBUG: print "PARSER DEBUG: unsolicited line completed"
        self.lines.append( self.curline )

        if self.hasPdu:
            if DEBUG: print "PARSER DEBUG: unsolicited line pdu completed, sending."
            if not self.curline:
                if DEBUG: print "Empty line before PDU, ignoring"
                # We have some cases where there is an empty line before the pdu
                self.lines.pop()
                return self.state_inline
            self.hasPdu = False
            self.unsolicited( self.lines )
            return self.reset()

        # Now this is slightly suboptimal. I tried hard to prevent even more protocol knowledge
        # infecting this parser, but I can't seem to find another way to detect a multiline
        # unsolicited response. Ideally, GSM would clearly indicate whether a PDU is following
        # or not, but alas, that's not the case.
        if self.curline:
            if self.curline.startswith( "+CBM:" ) \
            or self.curline.startswith( "+CDS:" ) \
            or self.curline.startswith( "+CMT:" ):
                if DEBUG: print "PARSER DEBUG: message has PDU, waiting for 2nd line."
                self.hasPdu = True
                self.curline = ""
                return self.state_inline
            else:
                self.unsolicited( self.lines )
                return self.reset()

        else:
            if DEBUG: print "PARSER DEBUG: unsolicited message with empty line. Ignoring."
            return self.state_inline

#=========================================================================#
LowlevelAtParser = StateBasedLowlevelAtParser
#=========================================================================#

#=========================================================================#
class ThrowStuffAwayParser( StateBasedLowlevelAtParser ):
#=========================================================================#
    """
    This parser has the ability to consume certain lines.
    """

    def __init__( self, trash, response, unsolicited ):
        StateBasedLowlevelAtParser.__init__( self, response, unsolicited )
        self.trash = trash

    def consume( self ):
        for t in self.trash:
            if self.curline.startswith( t ):
                print "PARSER: throwing away line starting with", t
                self.curline = ""
                return True # throw it away
        return False # process as usual

    def solicitedLineCompleted( self, multipleR = False ):
        if not self.consume():
            return StateBasedLowlevelAtParser.solicitedLineCompleted( self, multipleR )
        else:
            return self.state_inline

    def unsolicitedLineCompleted( self, multipleR = False ):
        if not self.consume():
            return StateBasedLowlevelAtParser.unsolicitedLineCompleted( self, multipleR )
        else:
            return self.state_inline

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

