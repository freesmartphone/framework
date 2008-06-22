#!/usr/bin/env python
"""
Open Device Daemon - Controller

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.0"

from framework.config import DBUS_BUS_NAME_PREFIX
from framework.config import LOG, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

import sys
import os

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from gobject import MainLoop, idle_add

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    LOG( LOG_ERR, "python-gobject >= 2.14.0 required" )
    
import ConfigParser
from optparse import OptionParser

#----------------------------------------------------------------------------#
class TheConfigParser( ConfigParser.SafeConfigParser ):
#----------------------------------------------------------------------------#
    def __init__( self, filename = None ):
        ConfigParser.SafeConfigParser.__init__( self )
        if filename is not None:
            self.read( filename )

#----------------------------------------------------------------------------#
class TheOptionParser( OptionParser ):
#----------------------------------------------------------------------------#
    def __init__( self ):
        OptionParser.__init__( self )
        self.set_defaults( overrides=[] )
        self.add_option("-o", "--override",
            dest="overrides",
            help="override configuration",
            metavar="SECTION.KEY=VALUE",
            action="append"
        )

#----------------------------------------------------------------------------#
class Controller( object ):
#----------------------------------------------------------------------------#
    """Loading and registering plugins"""
    def __init__( self, path ):
        self.objects = {}

        # dbus & glib mainloop
        DBusGMainLoop( set_as_default=True )
        self.mainloop = MainLoop()
        self.bus = dbus.SystemBus()
        self.busnames = []

        # call me
        idle_add( self.idle )
        timeout_add_seconds( 50, self.timeout )

        # config
        for p in [
                os.path.expanduser( "~/.frameworkd.conf" ),
                "/etc/frameworkd.conf", 
                os.path.join( os.path.dirname( __file__ ), "../conf/frameworkd.conf" )
            ]:
            if os.path.exists( p ):
                self.config = TheConfigParser( p )
                break
        else:
            self.config = TheConfigParser()

        # options
        self.options = TheOptionParser()
        self.options.parse_args()

        # overrides
        for override in self.options.values.overrides:
            left, value = override.split( '=', 1 )
            section, key = left.split( '.', 1 )
            if not self.config.has_section( section ):
                self.config.add_section( section )
            self.config.set( section, key, value )

        # walk subsystems and find 'em
        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]
        for subsystem in subsystems:
            # add blacklisting subsystems in configuration
            self.busnames.append( dbus.service.BusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ), self.bus ) )
            self.registerModulesInSubsystem( subsystem, path )

        LOG( LOG_INFO, "==================" )
        LOG( LOG_INFO, "objects registered" )
        LOG( LOG_INFO, "==================" )
        for obj in self.objects:
            LOG( LOG_INFO, obj )

    def registerModulesInSubsystem( self, subsystem, path ):
        LOG( LOG_DEBUG, "found subsystem %s" % subsystem )
        # walk the modules path and find plugins
        for filename in os.listdir( "%s/%s" % ( path, subsystem ) ):
            if filename.endswith( ".py" ): # FIXME: we should look for *.pyc, *.pyo, *.so as well
                try:
                    modulename = filename[:-3]
                    try:
                        disable = self.config.getboolean( modulename, "disable" )
                    except ConfigParser.Error:
                        disable = False
                    if disable:
                        LOG( LOG_INFO, "skipping module '%s' as requested in '%s'" % ( modulename, p ) )
                        continue
                    module = __import__(
                        name = ".".join( ["framework.subsystems", subsystem, modulename] ),
                        fromlist = ["factory"],
                        level = 0
                    )
                except ImportError, e:
                    LOG( LOG_ERR, "could not import %s: %s" % ( filename, e ) )
                except Exception, e:
                    LOG( LOG_ERR, "could not import %s: %s" % ( filename, e ) )
                else:
                    self.registerObjectsFromModule( subsystem, module, path )

    def registerObjectsFromModule( self, subsystem, module, path ):
        LOG( LOG_DEBUG, "...in subsystem %s: found module %s" % ( subsystem, module ) )
        try:
            factory = getattr( module, "factory" )
        except AttributeError:
            LOG( LOG_DEBUG, "no plugin: factory function not found in module %s" % module )
        else:
            try:
                for obj in factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ), self ):
                    self.objects[obj.path] = obj
            except Exception, e:
                    from traceback import format_exc
                    LOG( LOG_ERR, "factory method not successfully completed for module %s" % module )
                    LOG( LOG_ERR, format_exc() )

    def idle( self ):
        LOG( LOG_DEBUG, "in-mainloop initializer" )
        return False

    def timeout( self ):
        LOG( LOG_DEBUG, "regular timeout" )
        return True

    def run( self ):
        self.mainloop.run()
