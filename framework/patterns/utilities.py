#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: framework.patterns
Module: utilities
"""

import os, signal

import logging
logger = logging.getLogger( "mppl.utilities" )

#=========================================================================#
def processIterator():
#=========================================================================#
    for entry in os.listdir( "/proc" ):
        fileName = os.path.join( "/proc", entry, "cmdline" )
        if os.access( fileName, os.R_OK ):
            cmdline = file( fileName ).read()
            executablePath = cmdline.split("\x00")[0]
            executableName = executablePath.split(os.path.sep)[-1]
            #entry = pid, cmdline = cmdline file contents
            yield (entry, cmdline, executablePath, executableName)

#=========================================================================#
def processFinder(nameToFind, matchType):
#=========================================================================#
    for entry, cmdline, executablePath, executableName in processIterator():
        if matchType == "posix":
            if executableName == nameToFind:
                yield int( entry )
        elif matchType == "weak":
            if executablePath.find( nameToFind ) != -1:
                yield int( entry )
        elif matchType == "reallyweak":
            if cmdline.find( nameToFind ) != -1:
                yield int( entry )

#=========================================================================#
def killall( nameToKill, matchType="posix", killSignal=signal.SIGTERM ):
#=========================================================================#
    killedPids = []
    for pid in processFinder( nameToKill, matchType ):
        try:
            os.kill( pid, killSignal )
        except OSError, IOError: # permission denied/bad signal/process vanished/etc...
            pass
        else:
            killedPids.append( pid )
    return killedPids

