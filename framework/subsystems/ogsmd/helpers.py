#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
"""
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd
Module: helpers

"""

import os, signal

import logging
logger = logging.getLogger('ogsmd')

#========================================================================#
def writeToFile( path, value ):
#========================================================================#
    logger.debug( "(writing '%s' to '%s')" % ( value, path ) )
    try:
        f = open( path, 'w' )
    except IOError, e:
        logger.warning( "(could not write to '%s': %s)" % ( path, e ) )
    else:
        f.write( "%s\n" % value )

#=========================================================================#
def safesplit( string, delim, max=-1 ):
#=========================================================================#
    """A split function which is quote sign aware."""
    items = string.split(delim)
    safeitems = []
    safeitem = ""
    for i in items:
        safeitem = delim.join( [safeitem, i] )
        if safeitem.count('"')%2 == 0:
            safeitems.append( safeitem[1:] )
            safeitem = ""
    if max < len(safeitems):
        return safeitems[:max] + [delim.join(safeitems[max:])]
    else:
        return safeitems

#=========================================================================#
class BiDict( object ):
#=========================================================================#
    """A bidirectional dictionary."""

    AUTOINVERSE = False

    def __init__( self, adict = {} ):
        self._d = adict.copy()
        self._back = {}
        self._syncBack()

    def _syncBack( self ):
        for key, value in self._d.iteritems():
            self._back[value] = key
        assert len( self._d) == len( self._back ), "logic error"

    def __getitem__( self, key ):
        if not self.AUTOINVERSE:
            return self._d[key]
        else:
            try:
                return self._d[key]
            except KeyError:
                return self._back[key]

    def revlookup( self, key ):
        return self._back[key]

    def __setitem__( self, key, value ):
        if value in self._d:
            raise ValueError( "value is already a key" )
        elif key in self._back:
            raise ValueError( "key is already a value" )
        else:
            try:
                oldvalue = self._d[key]
            except KeyError:
                pass
            else:
                del self._back[oldvalue]
            self._d[key] = value
            self._back[value] = key
        assert len( self._d) == len( self._back ), "logic error"

    def __delitem__( self, key ):
        try:
            value = self._d[key]
        except KeyError:
            value = self._back[key]
            del self._back[key]
            del self._d[value]
        else:
            del self._d[key]
            del self._back[value]
        assert len( self._d) == len( self._back ), "logic error"

    def __repr__( self ):
        return "%s + %s" % ( self._d, self._back )

    def keys( self ):
        if not self.AUTOINVERSE:
            return self._d.keys()
        else:
            return self._d.keys() + self._back.keys()

#=========================================================================#
def processIterator():
#=========================================================================#
    for entry in os.listdir( "/proc" ):
        try:
            pid = int( entry )
        except ValueError:
            continue
        else:
            name = open( "/proc/%s/cmdline" % pid ).read().split( '\0' )[0]
            yield name, pid

#=========================================================================#
def killall( nameToKill ):
#=========================================================================#
    [ os.kill( pid, signal.SIGTERM ) for name, pid in processIterator() if name == nameToKill ]

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    d = BiDict( {"x":"y" } )

    d["foo"] = "bar"
    try:
        d["bar"] = 10 # should bail out
    except ValueError:
        pass
    else:
        assert False, "axiom violated"
    assert d["bar"] == "foo"

    del d["bar"]
