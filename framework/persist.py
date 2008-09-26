#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: persist

"""

from __future__ import with_statement

__version__ = "1.0.0"

import os, yaml, atexit

import logging
logger = logging.getLogger( "frameworkd.persist" )

from framework.config import config

class Persist( object ):
    def __init__( self, rootdir ):
        self.rootdir = rootdir
        self.cache = {}
        self.dirty = set()
        atexit.register( self._atexit )

    def _atexit( self ):
        for subsystem in list(self.dirty):
            logger.error( "dirty persist data for subsystem %s" % subsystem )
            self.sync( subsystem )

    def _load( self, subsystem ):
        if not subsystem in self.cache:
            try:
                filename = os.path.join( self.rootdir, subsystem+".yaml" )
                with file( filename, "r" ) as f:
                    data = yaml.safe_load( f.read() )
            except:
                data = {}
            self.cache[subsystem] = data

    def get( self, subsystem, key ):
        self._load( subsystem )
        return self.cache[subsystem].get( key, None )

    def set( self, subsystem, key, value ):
        self._load( subsystem )
        if value is None:
            self.cache[subsystem].pop( key, None )
        else:
            self.cache[subsystem][key] = value
        self.dirty.add( subsystem )

    def sync( self, subsystem ):
        if subsystem in self.dirty:
            filename = os.path.join( self.rootdir, subsystem+".yaml" )
            with file( filename, "w" ) as f:
                f.write( yaml.safe_dump( self.cache[subsystem] ) )
            self.dirty.discard( subsystem )

possible_rootdirs = os.path.abspath(
    config.getValue( "frameworkd.persist", "rootdir", "../etc/freesmartphone/persist:/etc/freesmartphone/persist:/usr/etc/freesmartphone/persist" )
).split(':')
for path in possible_rootdirs:
    if os.path.exists(path):
        persist = Persist(path)
        break
else:
    raise Exception("can't find the persistance root directory")

