#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: configparse
"""

__version__ = "1.0.0"

import ConfigParser
import types

#----------------------------------------------------------------------------#
class SmartConfigParser( ConfigParser.SafeConfigParser ):
#----------------------------------------------------------------------------#
    """
    A smart config parser
    """
    def __init__( self, filename = None ):
        ConfigParser.SafeConfigParser.__init__( self )
        self.filename = filename
        if filename is not None:
            self.read( filename )

    def sync( self ):
        # FIXME if we have a mainloop, collect sync calls and write deferred
        assert self.filename is not None, "no filename given yet"
        ConfigParser.SafeConfigParser.write( self, open(self.filename, "w" ) )

    def getOptions( self, section ):
        try:
            options = self.options( section )
        except ConfigParser.NoSectionError:
            return []
        else:
            return options

    def getValue( self, section, key, default=None, set=False, getmethod=ConfigParser.SafeConfigParser.get ):
        try:
            value = getmethod( self, section, key )
        except ConfigParser.NoSectionError:
            if set:
                self.add_section( section )
                self.set( section, key, str(default) )
                self.sync()
            return default
        except ConfigParser.NoOptionError:
            if set:
                self.set( section, key, str(default) )
                self.sync()
            return default
        else:
            return value

    def setValue( self, section, key, value ):
        try:
            self.set( section, key, str(value) )
        except ConfigParser.NoSectionError:
            self.add_section( section )
            self.set( section, key, str(value) )
        self.sync()

    def getBool( self, section, key, default=None, set=False ):
        return self.getValue( section, key, default, getmethod = ConfigParser.SafeConfigParser.getboolean )

    def getFloat( self, section, key, default=None, set=False ):
        return self.getValue( section, key, default, getmethod = ConfigParser.SafeConfigParser.getfloat )

    def getInt( self, section, key, default=None, set=False ):
        return self.getValue( section, key, default, getmethod = ConfigParser.SafeConfigParser.getint )

    def getSetDefault( self, section, key, default ):
        """
        The type to return is gathered from the type of the default value.

        If the section does not exist, it is created.
        If the key does not exist, it is created with the default value.
        """
        value = self.getValue( section, key, default, True )
        return self._typedValue( value, default )

    def getDefault( self, section, key, default ):
        """
        The type to return is gathered from the type of the default value.
        """
        value = self.getValue( section, key, default, False )
        #print "value =", value, "returning", self._typedValue( value, default )
        return self._typedValue( value, default )

    def _typedValue( self, value, default ):
        valuetype = type( default )
        if valuetype == types.StringType:
            return str( value )
        elif valuetype == types.IntType:
            return int( value )
        elif valuetype == types.BooleanType:
            return bool( value )
        elif valuetype == types.FloatType:
            return float( value )
        else: # can't guess type, return it unchanged
            return value

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    FILENAME = "/tmp/test.ini"
    import os
    try:
        os.unlink( FILENAME )
    except OSError: # might not exist
        pass
    c = SmartConfigParser( FILENAME )

    print "TESTING...",

    # reading a non existent key
    assert c.getDefault( "foo.bar", "key", None ) == None
    assert c.getDefault( "foo.bar", "key", False ) == False
    assert c.getDefault( "foo.bar", "key", 10 ) == 10
    assert c.getDefault( "foo.bar", "key", 10.0 ) == 10.0
    assert c.getDefault( "foo.bar", "key", "10" ) == "10"

    # getset a key
    assert c.getSetDefault( "foo.bar", "key", 500 ) == 500
    assert c.getDefault( "foo.bar", "key", 100 ) == 500

    print "OK."
