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

import os, atexit

import logging
logger = logging.getLogger( "frameworkd.persist" )

from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'persist' )
format = config.getValue( "frameworkd", "persist_format", "pickle" )

if format == "pickle":
    import pickle
elif format == "yaml":
    from yaml import load, dump
    try:
        from yaml import CLoader as Loader
        from yaml import CDumper as Dumper
    except ImportError:
        from yaml import Loader, Dumper

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
                filename = os.path.join( self.rootdir, subsystem+"."+format )
                with file( filename, "r" ) as f:
                    data = f.read()
            except:
                logger.error( "no persist data for subsystem %s" % subsystem )
                data = ""
            if data == "": # empty file
                data = {}
            elif format == "pickle":
                data = pickle.loads( data )
            elif format == "yaml":
                data = load( data, Loader=Loader )
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
            if format == "pickle":
                data = pickle.dumps( self.cache[subsystem], protocol = 2 )
            elif format == "yaml":
                data = dump( self.cache[subsystem], Dumper=Dumper )
            filename = os.path.join( self.rootdir, subsystem+"."+format )
            with file( filename+".tmp", "w" ) as f:
                f.write( data )
            os.rename( filename+".tmp", filename )
            self.dirty.discard( subsystem )

persist = Persist( rootdir )


