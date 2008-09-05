#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: controller
"""

__version__ = "0.9.4"

from framework.config import DBUS_BUS_NAME_PREFIX, debug, config, loggingmap
from optparse import OptionParser
import subsystem

import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gobject import MainLoop, idle_add
import os, sys, types

import logging
logger = logging.getLogger( "frameworkd.controller" )

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    logger.error( "python-gobject >= 2.14.0 required" )
    sys.exit( -1 )

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
    # We store all the DBUs object in a class attribute
    objects = {}

    @classmethod
    def object( cls, name ):
        """
        Return a DBus object -not proxy- from the list of registered objects.
        If there is no such object, return None
        """
        return cls.objects.get( name, None )

    def __init__( self, path ):
        # dbus & glib mainloop
        DBusGMainLoop( set_as_default=True )
        self.mainloop = MainLoop()
        self.bus = dbus.SystemBus()

        # check if there's already something owning our bus name org.freesmartphone.frameworkd
        if "%s.frameworkd" % DBUS_BUS_NAME_PREFIX in self.bus.list_names():
            logger.error( "dbus bus name org.freesmartphone.frameworkd already claimed. Exiting." )
            sys.exit( -1 )

        self._subsystems = {}
        self.busnames = []
        # FIXME remove hardcoded controller knowledge from objects
        self.config = config

        # call me
        idle_add( self.idle )
        timeout_add_seconds( 50, self.timeout )

        self._configureLoggers()
        self._handleOverrides()

        self._subsystems["frameworkd"] = subsystem.Framework( self.bus, path, self )
        Controller.objects.update( self._subsystems["frameworkd"].objects() )

        # walk subsystems and find 'em
        systemstolaunch = self.options.values.subsystems.split( ',' )

        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]

        for s in subsystems:
            disable = config.getBool( s, "disable", False )
            if disable:
                logger.info( "skipping subsystem %s as requested via config file." % s )
                continue
            if systemstolaunch != [""]:
                if s not in systemstolaunch:
                    logger.info( "skipping subsystem %s as requested via command line" % s )
                    continue
                logger.info( "launching subsystem %s" % s )
                self._subsystems[s] = subsystem.Subsystem( s, self.bus, path, self )
            else:
                self._subsystems[s] = subsystem.Subsystem( s, self.bus, path, self )
            Controller.objects.update( self._subsystems[s].objects() )

        # do we have any subsystems left?
        if not self.options.values.debug:
            if len( self._subsystems ) == 1: # no additional subsystems could be loaded
                logger.error( "can't launch without at least one subsystem. Exiting." )
                sys.exit( -1 )

        logger.info( "================== objects registered ===================" )
        objectnames = Controller.objects.keys()
        objectnames.sort()
        for obj in objectnames:
            logger.info( "%s [%s]" % ( obj, Controller.objects[obj].interface ) )

    def subsystems( self ):
        return self._subsystems

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
        """
        Regular timeout.
        """
        # FIXME add self-monitoring and self-healing
        logger.debug( "alive and kicking" )
        return True # call me again

    def run( self ):
        self.mainloop.run()

    #
    # private API
    #
    def _configureLoggers( self ):
        # configure all loggers, default being INFO
        for section in config.sections():
            loglevel = loggingmap.get( config.getValue( section, "log_level", debug ) )
            logger.debug( "setting logger for %s to %s" % ( section, loglevel ) )
            logging.getLogger( section ).setLevel( loglevel )
        # FIXME configure handlers

    def _handleOverrides( self ):
        self.options = TheOptionParser()
        self.options.parse_args()
        self.config = config

        for override in self.options.values.overrides:
            try:
                left, value = override.split( '=', 1 )
                section, key = left.split( '.', 1 )
            except ValueError:
                self.options.error( "Wrong format for override values" )
            if not self.config.has_section( section ):
                self.config.add_section( section )
            self.config.set( section, key, value )

    def _nameOwnerChanged( self, name_owner, *args ):
        pass

#----------------------------------------------------------------------------#
if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

