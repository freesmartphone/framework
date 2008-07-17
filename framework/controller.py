#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.0"

from framework.config import DBUS_BUS_NAME_PREFIX
from framework.config import LOG, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gobject import MainLoop, idle_add
import os
import sys
import types

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    LOG( LOG_ERR, "python-gobject >= 2.14.0 required" )
    sys.exit( -1 )

import ConfigParser
from optparse import OptionParser
from .configparse import SmartConfigParser

#----------------------------------------------------------------------------#
class TheOptionParser( OptionParser ):
#----------------------------------------------------------------------------#
    def __init__( self ):
        OptionParser.__init__( self )
        self.set_defaults( overrides=[] )
        self.add_option( "-o", "--override",
            dest = "overrides",
            help = "override configuration",
            metavar = "SECTION.KEY=VALUE",
            action = "append"
        )
        self.add_option( "-s", "--subsystems",
            metavar = "system1,system2,system3,...",
            dest = "subsystems",
            default = "",
            help = "launch following subsystems (default=all)",
            action = "store",
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
                LOG( LOG_INFO, "Using configuration file", p )
                self.config = SmartConfigParser( p )
                break
        else:
            self.config = SmartConfigParser( "~/.frameworkd.conf" )

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

        # framework subsystem / management object will always be there
        subsystem = "frameworkd"
        from .objectquery import factory
        ok = self.tryClaimBusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ) )
        if not ok:
            LOG( LOG_ERR, "Unable to claim master bus name. Exiting." )
            sys.exit( -1 )
        self.framework = factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ), self )

        # walk subsystems and find 'em
        systemstolaunch = self.options.values.subsystems.split( ',' )

        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]
        for subsystem in subsystems:
            if systemstolaunch != [""]:
                if subsystem not in systemstolaunch:
                    LOG( LOG_INFO, "skipping subsystem", subsystem, "due to command line configuration" )
                    continue
                else:
                    LOG( LOG_INFO, "launching subsystem", subsystem )
            if self.tryClaimBusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ) ):
                self.registerModulesInSubsystem( subsystem, path )

        LOG( LOG_INFO, "==================" )
        LOG( LOG_INFO, "objects registered" )
        LOG( LOG_INFO, "==================" )
        objectnames = self.objects.keys()
        objectnames.sort()
        for obj in objectnames:
            LOG( LOG_INFO, obj, "[%s]" % self.objects[obj].interface )

    def tryClaimBusName( self, busname ):
        try:
            self.busnames.append( dbus.service.BusName( busname, self.bus ) )
            return True
        except dbus.DBusException:
            LOG( LOG_WARNING, "Can't claim bus name '%s', check configuration in /etc/dbus-1/system.d/frameworkd.conf -- ignoring subsystem." % busname )
            return False

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

#----------------------------------------------------------------------------#
if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

