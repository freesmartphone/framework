#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: framework.patterns
Module: loophole
"""

__version__ = "0.1.0"

import SocketServer
import thread
import code
import sys

import gobject
gobject.threads_init()

if __debug__:
    class logger():
        @staticmethod
        def debug( message ):
            print message
else:
    import logging
    logger = logging.getLogger( "mppl.loophole" )

#============================================================================#
class Writer( object ):
#============================================================================#
    def __init__( self, delegate ):
        self.delegate = delegate

    def write( self, data ):
        self.delegate( data )

#============================================================================#
class NetworkInterpreterConsole( code.InteractiveConsole ):
#============================================================================#
    def __init__( self, request, locals_, *args, **kwargs ):
        self.request = request
        self.exitflag = False
        code.InteractiveConsole.__init__( self, locals_, *args, **kwargs )

        self.oldstdout = sys.stdout
        sys.stdout = Writer( self.write )

    def raw_input( self, prompt ):
        self.request.send( prompt )
        print >>self.oldstdout, "waiting for data..."
        data = self.request.recv( 1024 )
        print >>self.oldstdout, "got data '%s'" % repr(data)

        if data == "\x04":
            raise EOFError

        return data[:-2] # omit trailing \r\n

    def close( self ):
        self.exitflag = True
        sys.stdout = self.oldstdout
        del self.oldstdout

    def write( self, data ):
        if not self.exitflag:
            self.request.send( data )

#============================================================================#
class InterpreterRequestHandler( SocketServer.BaseRequestHandler ):
#============================================================================#
    """
    Request Handler
    """
    interpreters = {}

    def setup( self ):
        try:
            self.myinterpreter = self.interpreters[self.client_address]
        except KeyError:
            self.myinterpreter = self.interpreters[self.client_address] = NetworkInterpreterConsole( self.request, self.locals_ )

    def handle( self ):
        self.myinterpreter.interact()

    def finish( self ):
        self.myinterpreter.close()
        self.request.send( "Bye %s\n" % str( self.client_address ) )
        self.request.close()

#============================================================================#
class LoopHole( object ):
#============================================================================#
    def __init__( self, locals_  = {} ):
        InterpreterRequestHandler.locals_ = locals_
        self.server = SocketServer.ThreadingTCPServer( ( "", 8822 ), InterpreterRequestHandler )
        thread.start_new_thread( self.run, () )

    def run( self, *args, **kwargs ):
        self.server.serve_forever()

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    import time

    l = LoopHole()
    try:
        while True:
            time.sleep( 10 )
    except KeyboardInterrupt:
        pass

    sys.exit( 0 )