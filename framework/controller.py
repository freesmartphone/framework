#!/usr/bin/env python
"""
Open Device Daemon - Controller

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.0"

from config import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX
from config import LOG, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from gobject import MainLoop, idle_add

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    from gobject import timeout_add
    def timeout_add_seconds( timeout, callback ):
        return timeout_add( 1000 * timeout, callback )

import ConfigParser
import sys
import os

#----------------------------------------------------------------------------#
class TheConfigParser( ConfigParser.SafeConfigParser ):
#----------------------------------------------------------------------------#
    def __init__( self, filename = None ):
        ConfigParser.SafeConfigParser.__init__( self )
        if filename is not None:
            self.read( filename )

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
        self.busname = dbus.service.BusName( DBUS_INTERFACE_PREFIX, self.bus )

        # call me
        idle_add( self.idle )
        timeout_add_seconds( 50, self.timeout )

        # config
        for p in [ os.path.expanduser( "~/.frameworkd.conf" ), "/etc/frameworkd.conf" ]:
            if os.path.exists( p ):
                self.config = TheConfigParser( p )
                break
        else:
            self.config = TheConfigParser()

        # walk subsystems and find 'em
        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s/modules" % ( path, entry ) ) ]
        for subsystem in subsystems:
            # add blacklisting subsystems in configuration
            self.registerSubsystem( subsystem, path )

    def registerSubsystem( self, subsystem, path ):
        LOG( LOG_INFO, "found subsystem %s" % subsystem )
        # walk the modules path and find plugins
        for filename in os.listdir( "%s/%s/modules" % ( path, subsystem ) ):
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
                        name = ".".join( ["subsystems", subsystem, "modules", modulename] ),
                        fromlist = ["factory"],
                        level = 0
                    )
                except ImportError, e:
                    LOG( LOG_ERR, "could not import %s: %s" % ( filename, e ) )
                except Exception, e:
                    LOG( LOG_ERR, "could not import %s: %s" % ( filename, e ) )
                else:
                    self.registerModule( subsystem, module, path )

    def registerModule( self, subsystem, module, path ):
        LOG( LOG_INFO, "...in subsystem %s: found module %s" % ( subsystem, module ) )
        try:
            factory = getattr( module, "factory" )
        except AttributeError:
            LOG( LOG_INFO, "no plugin: factory function not found in module %s" % module )
        else:
            for obj in factory( DBUS_INTERFACE_PREFIX, self ):
                self.objects[obj.path] = obj
            LOG( LOG_INFO, "ok" )

    def idle( self ):
        LOG( LOG_DEBUG, "in-mainloop initializer" )
        return False

    def timeout( self ):
        LOG( LOG_DEBUG, "regular timeout" )
        return True

    def run( self ):
        self.mainloop.run()
