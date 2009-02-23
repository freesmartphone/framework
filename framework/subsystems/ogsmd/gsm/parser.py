#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: parser
"""

__version__ = "0.8.1"

import os
DEBUG = os.environ.get( "FSO_DEBUG_PARSER", False )

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

    def reset( self, yankSolicited=True ):
        if yankSolicited:
            self.lines = []
        self.ulines = []
        self.curline = ""
        self.hasPdu = False
        return self.state_start

    def feed( self, bytes, haveCommand, validPrefixes ):
        # NOTE: the continuation query relies on '\r\n> ' not being
        # fragmented... question: is that always correct? If not,
        # we better keep the state. We could also enhance the signature
        # to support handing a haveContinuation parameter over to here.

        self.haveCommand = haveCommand
        self.validPrefixes = validPrefixes

        if bytes == "\r\n> ":
            if DEBUG: print "PARSER DEBUG: got continuation character. sending empty response"
            self.response( [] )
            self.state = self.reset()
            return

        for b in bytes:
            if DEBUG: print "PARSER DEBUG: [%s] feeding %s to %s" % ( ( "solicited" if self.haveCommand else "unsolicited" ), repr(b), self.state )

            nextstate = self.state( b )
            if nextstate is None:
                print "PARSER DEBUG: WARNING: UNDEFINED PARSER STATE! Do not know where to go from %s upon receiving %s" % ( self.state, repr(b) )
                print "previous bytes were:", repr(bytes)
                print "current byte is:", repr(b)
                print "lines:", repr(self.lines)
                print "curline:", repr(self.curline)
                print "solicited:", self.haveCommand
                self.state = self.reset()
                break
            else:
                self.state = nextstate

    def state_start( self, b ):
        if b == '\r':
            return self.state_start_r
        # this is unusal, but we are forgiving
        if b == '\n':
            return self.state_inline
        # this is even more unusual, but we are _really_ forgiving
        return self.state_inline( b )

    def state_start_r( self, b ):
        if b == '\n':
            return self.state_inline

    def state_inline( self, b ):
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
                return self.lineCompleted()

    def state_inline_r( self, b ):
        if b == '\r':
            return self.state_inline_multipleR
        if b == '\n':
            return self.lineCompleted()

    def state_inline_multipleR( self, b ):
        if b == '\r':
            return self.state_inline_multipleR
        if b == '\n':
            return self.lineCompleted( True )

    def lineCompleted( self, multipleR = False ):
        if self.haveCommand:
            return self.solicitedLineCompleted( multipleR )
        else:
            return self.unsolicitedLineCompleted( multipleR )

    def solicitedLineCompleted( self, multipleR = False ):
        if DEBUG: print "PARSER DEBUG: [perhaps solicited] line completed, line=", repr(self.curline), "previous lines=", self.lines

        if self.isTerminationLine():
            if DEBUG: print "PARSER DEBUG: [solicited] response completed"
            self.lines.append( self.curline )
            self.response( self.lines )
            return self.reset()

        elif self.hasPdu:
            self.hasPdu = False
            self.lines.append( self.curline )
            self.curline = ""
            return self.state_start

        elif self.isUnsolicitedLine():
            if DEBUG: print "PARSER DEBUG: [unsolicited] response detected within solicited"
            return self.unsolicitedLineCompleted( multipleR )

        else:
            self.hasPdu = self.isSolicitedPduLine()
            self.lines.append( self.curline )
            self.curline = ""
            return self.state_start

    def isUnsolicitedLine( self ):
        """
        Check whether the line starts with a prefix that indicates a valid response to our command.
        """
        if self.validPrefixes == []: # everything allowed
            return False
        for prefix in self.validPrefixes:
            if DEBUG: print "PARSER DEBUG: checking whether %s starts with valid prefix %s" % ( repr(self.curline), repr(prefix) )
            if self.curline.startswith( prefix ):
                if DEBUG: print "PARSER DEBUG: yes; must be really solicited"
                return False
        if DEBUG: print "PARSER DEBUG: no match; must be unsolicited"
        return True # no prefix did match

    def isTerminationLine( self ):
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
            return True
        else:
            return False

    def isUnsolicitedPduLine( self ):
        if self.curline.startswith( "+CBM:" ) \
        or self.curline.startswith( "+CDS:" ) \
        or self.curline.startswith( "+CMT:" ):
            return True
        else:
            return False

    def isSolicitedPduLine( self ):
        if self.curline.startswith( "+CMGL:" ):
            return True
        else:
            return False

    def unsolicitedLineCompleted( self, multipleR = False ):
        if DEBUG: print "PARSER DEBUG: [unsolicited] line completed, line=", repr(self.curline)
        self.ulines.append( self.curline )

        if self.hasPdu:
            if DEBUG: print "PARSER DEBUG: [unsolicited] line pdu completed, sending."
            if not self.curline:
                if DEBUG: print "Empty line before PDU, ignoring"
                # We have some cases where there is an empty line before the pdu
                self.ulines.pop()
                return self.state_inline
            self.hasPdu = False
            self.unsolicited( self.ulines )
            return self.reset( False )

        # Now this is slightly suboptimal. I tried hard to prevent even more protocol knowledge
        # infecting this parser, but I can't seem to find another way to detect a multiline
        # unsolicited response. Ideally, GSM would clearly indicate whether a PDU is following
        # or not, but alas, that's not the case.
        if self.curline:
            if self.isUnsolicitedPduLine():
                if DEBUG: print "PARSER DEBUG: message has PDU, waiting for 2nd line."
                self.hasPdu = True
                self.curline = ""
                return self.state_inline
            else:
                self.unsolicited( self.ulines )
                return self.reset( False )
        else:
            if DEBUG: print "PARSER DEBUG: [unsolicited] message with empty line. Ignoring."
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
class AlwaysUnsolicitedParser( StateBasedLowlevelAtParser ):
#=========================================================================#
    """
    This parser treats certain responses always as unsolicited, based on
    prefix matching. It is useful for modems which do not support deferring
    unsolicited responses between sending a query and returning the (solicited)
    response -- such as the TI Calypso with regards to +CRING, +CLIP, and %CPI.
    """

    def __init__( self, alwaysUnsolicited, response, unsolicited ):
        StateBasedLowlevelAtParser.__init__( self, response, unsolicited )
        self.alwaysUnsolicited = alwaysUnsolicited

    def lineCompleted( self, multipleR = False ):
        # FIXME update self.haveCommand for next command
        if self.haveCommand and not self.isAlwaysUnsolicited():
            return self.solicitedLineCompleted( multipleR )
        else:
            return self.unsolicitedLineCompleted( multipleR )

    def isAlwaysUnsolicited( self ):
        for u in self.alwaysUnsolicited:
            if self.curline.startswith( u ):
                return True
        return False

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

