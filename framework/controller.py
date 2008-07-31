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
import os, sys, types

import logging
logger = logging.getLogger( "frameworkd.controller" )

loggingmap = { \
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    }

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    logger.error( "python-gobject >= 2.14.0 required" )
    sys.exit( -1 )

from optparse import OptionParser
from .config import config
import subsystem

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
        # FIXME remove
        self.objects = {}

        # dbus & glib mainloop
        DBusGMainLoop( set_as_default=True )
        self.mainloop = MainLoop()
        self.bus = dbus.SystemBus()
        self.subsystems = {}
        self.busnames = []
        # FIXME remove hardcoded controller knowledge from objects
        self.config = config

        # call me
        idle_add( self.idle )
        timeout_add_seconds( 50, self.timeout )

        self._configureLoggers()
        self._handleOverrides()

        self.subsystems["frameworkd"] = subsystem.Framework( self.bus, path, self )
        self.objects.update( self.subsystems["frameworkd"].objects() )

        # walk subsystems and find 'em
        systemstolaunch = self.options.values.subsystems.split( ',' )

        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]

        for s in subsystems:
            if systemstolaunch != [""]:
                if s not in systemstolaunch:
                    logger.info( "skipping subsystem %s due to command line configuration" % s )
                    continue
                else:
                    logger.info( "launching subsystem %s" % s )
                    self.subsystems[s] = subsystem.Subsystem( s, self.bus, path, self )
            else:
                self.subsystems[s] = subsystem.Subsystem( s, self.bus, path, self )
            self.objects.update( self.subsystems[s].objects() )


        if not self.options.values.debug:
            if len( self.subsystems ) == 1: # no additional subsystems could be loaded
                logger.error( "can't launch without at least one subsystem. Exiting." )
                sys.exit( -1 )

        logger.info( "================== objects registered ===================" )
        objectnames = self.objects.keys()
        objectnames.sort()
        for obj in objectnames:
            logger.info( "%s [%s]" % ( obj, self.objects[obj].interface ) )

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
            loglevel = loggingmap.get( config.getValue( section, "log_level", "INFO" ) )
            logger.info( "setting logger for %s to %s" % ( section, loglevel ) )
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

    # FIXME remove hard-coded controller knowledge from module, this wasn't supposed to be a public API!
    def tryClaimBusName( self, name ):
        """
        Claim a dbus bus name.
        """
        try:
            self.foo = dbus.service.BusName( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, name ), self.bus )
            return True
        except dbus.DBusException:
            logger.warning( "Can't claim bus name '%s', check configuration in /etc/dbus-1/system.d/frameworkd.conf -- ignoring subsystem." % name )
            return False


#----------------------------------------------------------------------------#
if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

