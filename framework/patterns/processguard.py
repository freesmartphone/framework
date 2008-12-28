#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework.patterns
Module: processguard
"""

__version__ = "0.0.0"

import gobject

import os

MAX_READ = 4096

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
        self._childwatch = None
        self._stdoutwatch = None
        self._stderrwatch = None
        self._cmdline = cmdline.split()
        self._reset()

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
                                      child_setup=None,
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
        if self._onError is not None:
            self._onError( data )
        return True # mainloop: call me again

    def _exitFromChild( self, pid, condition, data=None ):
        """
        Called after(!) child has exit
        """
        exitcode = (condition >> 8) & 0xFF
        exitsignal = condition & 0xFF
        pid = self.pid
        self._reset() # self.pid now None
        if self._onExit is not None:
            self._onExit( pid, exitcode, exitsignal )

    def __del__( self ):
        """
        Cleanup
        """
        if self.pid is not None:
            os.kill( self.pid, 1 )
            self.reset()

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
