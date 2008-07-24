#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.9.1"

from framework.config import DBUS_BUS_NAME_PREFIX

import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gobject import MainLoop, idle_add
import os
import sys
import types

import logging
logger = logging.getLogger('frameworkd')

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    logger.error( "python-gobject >= 2.14.0 required" )
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
        self.add_option( "-d", "--debug",
            dest = "debug",
            help = "launch in debug mode",
            action = "store_true",
        )

#----------------------------------------------------------------------------#
class Controller( object ):
#----------------------------------------------------------------------------#
    """
    Loading and registering plugins.
    """
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
                logger.info( "Using configuration file %s" % p )
                self.config = SmartConfigParser( p )
                break
        else:
            self.config = SmartConfigParser( "~/.frameworkd.conf" )

        # options
        self.options = TheOptionParser()
        self.options.parse_args()

        # overrides
        for override in self.options.values.overrides:
            try:
                left, value = override.split( '=', 1 )
                section, key = left.split( '.', 1 )
            except ValueError:
                self.options.error( "Wrong format for override values" )
            if not self.config.has_section( section ):
                self.config.add_section( section )
            self.config.set( section, key, value )

        # Set the logging levels :
        for section in self.config.sections():
            debuglevel = self.config.getValue( section, 'log_level', default = 'INFO' )
            logger.debug("set %s log level to %s" % ( section, debuglevel ) )
            debuglevel = getattr(logging, debuglevel)
            logging.getLogger(section).setLevel(debuglevel)

        # framework subsystem / management object will always be there
        subsystem = "frameworkd"
        from .objectquery import factory
        ok = self.tryClaimBusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ) )
        if not ok:
            logger.error( "Unable to claim master bus name. Exiting." )
            sys.exit( -1 )
        self.framework = factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ), self )

        # walk subsystems and find 'em
        systemstolaunch = self.options.values.subsystems.split( ',' )

        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]
        for subsystem in subsystems:
            if systemstolaunch != [""]:
                if subsystem not in systemstolaunch:
                    logger.info( "skipping subsystem %s due to command line configuration" % subsystem )
                    continue
                else:
                    logger.info( "launching subsystem %s" % subsystem )
            if self.tryClaimBusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ) ):
                self.registerModulesInSubsystem( subsystem, path )

        if not self.options.values.debug:
            if len( self.busnames ) == 1: # no additional subsystems could be loaded
                logger.error( "can't launch without at least one subsystem. Exiting." )
                sys.exit( -1 )

        logger.info( "==================" )
        logger.info( "objects registered" )
        logger.info( "==================" )
        objectnames = self.objects.keys()
        objectnames.sort()
        for obj in objectnames:
            logger.info( "%s [%s]" % ( obj, self.objects[obj].interface ) )

    def tryClaimBusName( self, busname ):
        try:
            self.busnames.append( dbus.service.BusName( busname, self.bus ) )
            return True
        except dbus.DBusException:
            logger.warning( "Can't claim bus name '%s', check configuration in /etc/dbus-1/system.d/frameworkd.conf -- ignoring subsystem." % busname )
            return False

    def registerModulesInSubsystem( self, subsystem, path ):
        logger.debug( "found subsystem %s" % subsystem )
        # walk the modules path and find plugins
        for filename in os.listdir( "%s/%s" % ( path, subsystem ) ):
            if filename.endswith( ".py" ): # FIXME: we should look for *.pyc, *.pyo, *.so as well
                try:
                    modulename = filename[:-3]
                    try:
                        #XXX: if the name of the file is not the same than the name of the module
                        #     e.g : gsm.py instead of ogsmd.py, then this line is useless
                        disable = self.config.getboolean( modulename, "disable" )
                    except ConfigParser.Error:
                        disable = False
                    if disable:
                        logger.info( "skipping module '%s' as requested in config." % ( modulename ) )
                        continue
                    module = __import__(
                        name = ".".join( ["framework.subsystems", subsystem, modulename] ),
                        fromlist = ["factory"],
                        level = 0
                    )
                except ImportError, e:
                    logger.error( "could not import %s: %s" % ( filename, e ) )
                except Exception, e:
                    logger.error( "could not import %s: %s" % ( filename, e ) )
                else:
                    self.registerObjectsFromModule( subsystem, module, path )

    def registerObjectsFromModule( self, subsystem, module, path ):
        logger.debug( "...in subsystem %s: found module %s" % ( subsystem, module ) )
        try:
            factory = getattr( module, "factory" )
        except AttributeError:
            logger.debug( "no plugin: factory function not found in module %s" % module )
        else:
            try:
                for obj in factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, subsystem ), self ):
                    self.objects[obj.path] = obj
            except Exception, e:
                    from traceback import format_exc
                    logger.error( "factory method not successfully completed for module %s" % module )
                    logger.error( format_exc() )

    def idle( self ):
        logger.debug( "entered mainloop" )
        #self.bus.add_signal_receiver(
            #self._nameOwnerChanged,
            #"NameOwnerChanged",
            #"org.freedesktop.DBus",
            #"org.freedesktop.DBus",
            #"/org/freedesktop/DBus",
            #sender_keyword = None,
            #destination_keyword = None,
            #interface_keyword = None,
            #member_keyword = None,
            #path_keyword = None )

        return False # don't call me again

    def timeout( self ):
        logger.debug( "alive and kicking" )
        return True # call me again

    def run( self ):
        self.mainloop.run()

    def _nameOwnerChanged( self, name_owner, *args ):
        pass

#----------------------------------------------------------------------------#
if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

