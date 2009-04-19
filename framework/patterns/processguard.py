#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: framework.patterns
Module: processguard
"""

__version__ = "0.3.0"

import gobject

import os, signal, types

MAX_READ = 4096

import logging
logger = logging.getLogger( "mppl.processguard" )

#============================================================================#
class ProcessGuard( object ):
#============================================================================#
    #
    # private
    #
    def __init__( self, cmdline ):
        """
        Init
        """
        if type( cmdline ) == types.ListType:
            self._cmdline = cmdline
        else:
            self._cmdline = cmdline.split()
        self._childwatch = None
        self._stdoutwatch = None
        self._stderrwatch = None
        self.hadpid = None
        self._reset()
        logger.debug( "Created process guard for %s" % repr(self._cmdline) )

    def _reset( self ):
        """
        Reset
        """
        self.pid = None
        self.stdin = None
        self.stdout = None
        self.stderr = None

        if self._childwatch is not None:
            gobject.source_remove( self._childwatch )
            self._childwatch = None
        if self._stdoutwatch is not None:
            gobject.source_remove( self._stdoutwatch )
            self._stdoutwatch = None
        if self._stderrwatch is not None:
            gobject.source_remove( self._stderrwatch )
            self._stderrwatch = None

    def _execute( self, options ):
        """
        Launch the monitored process
        """
        if options is None:
            cmdline = self._cmdline
        else:
            cmdline = [self._cmdline[0]] + options.split()

        result = gobject.spawn_async( cmdline,
                                      envp="",
                                      working_directory=os.environ.get( "PWD", "/" ),
                                      flags=gobject.SPAWN_DO_NOT_REAP_CHILD, # needed for child watch
                                      user_data=None,
                                      standard_input=False,
                                      standard_output=True,
                                      standard_error=True )
        if result[0] < 0:
            raise OSError( "foo" )

        self.pid, self.stdin, self.stdout, self.stderr = result

        self._childwatch = gobject.child_watch_add( self.pid, self._exitFromChild, priority=100 )
        self._stdoutwatch = gobject.io_add_watch( self.stdout, gobject.IO_IN, self._outputFromChild )
        self._stderrwatch = gobject.io_add_watch( self.stderr, gobject.IO_IN, self._errorFromChild )

    def _outputFromChild( self, source, condition ):
        """
        Called on child output
        """
        if condition != gobject.IO_IN:
            return False
        data = os.read( source, MAX_READ )
        logger.debug( "%s got data from child: %s" % ( self, repr(data) ) )
        if self._onOutput is not None:
            self._onOutput( data )
        return True # mainloop: call me again

    def _errorFromChild( self, source, condition ):
        """
        Called on child output (stderr)
        """
        if condition != gobject.IO_IN:
            return False
        data = os.read( source, MAX_READ )
        logger.debug( "%s got error from child: %s" % ( self, repr(data) ) )
        if self._onError is not None:
            self._onError( data )
        return True # mainloop: call me again

    def _exitFromChild( self, pid, condition, data=None ):
        """
        Called after(!) child has exit
        """
        exitcode = (condition >> 8) & 0xFF
        exitsignal = condition & 0xFF

        self.hadpid = pid
        self._reset() # self.pid now None

        if self._onExit is not None:
            self._onExit( pid, exitcode, exitsignal )

    def __del__( self ):
        """
        Cleanup
        """
        self.shutdown()
        self._reset()

    #
    # API
    #
    def execute( self, options=None, onExit=None, onError=None, onOutput=None ):
        """
        Launch the process

        Optionally override parameters and setup delegates.
        """
        self._onExit = onExit
        self._onOutput = onOutput
        self._onError = onError
        self._execute( options )

    def shutdown( self, sig=signal.SIGTERM ):
        """
        Shutdown the process.
        """
        if self.pid is not None:
            logger.info( "shutdown: killing process %d with signal %d", self.pid, sig )
            try:
                os.kill( self.pid, sig )
            except OSError:
                logger.info( "shutdown: process already vanished" )
        else:
            logger.info( "shutdown: process already vanished" )

    def isRunning( self ):
        """
        Returns True, when the process is running. False, otherwise.
        """
        return self.pid is not None

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    def firstExit( pid, exitcode, exitsignal ):
        print "first exit"
        p.execute( "/tmp", onExit=secondExit )

    def secondExit( pid, exitcode, exitsignal ):
        print "second exit"

    loop = gobject.MainLoop()

    p = ProcessGuard( "/bin/ls ." )
    p.execute( onExit=firstExit )

    try:
        loop.run()
    except KeyboardInterrupt:
        loop.quit()
    else:
        print "oK"
