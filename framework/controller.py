#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: controller
"""

MODULE_NAME = "frameworkd.controller"
__version__ = "0.9.8"

from framework.config import DBUS_BUS_NAME_PREFIX, debug, config, loggingmap
from framework.patterns import daemon
import subsystem

import dbus, dbus.service, dbus.mainloop.glib
import gobject
import os, sys, types, time

import logging
logger = logging.getLogger( MODULE_NAME )

try: # not present in older glib versions
    from gobject import timeout_add_seconds
except ImportError:
    logger.error( "python-gobject >= 2.14.0 required" )
    sys.exit( -1 )

#----------------------------------------------------------------------------#
class Controller( daemon.Daemon ):
#----------------------------------------------------------------------------#
    """
    Loading and registering plugins.
    """
    # We store all DBus objects in a class attribute
    objects = {}

    @classmethod
    def object( cls, name ):
        """
        Return a DBus object -not proxy- from the list of registered objects.
        """
        return cls.objects[name]

    def __init__( self, path, options ):
        sys.path.append( path ) # to enable 'from <subsystemname> import ...' and 'import <subsystemname>'
        self.launchTime = time.time()
        self.options = options
        daemon.Daemon.__init__( self, "/tmp/frameworkd.pid" )

        # dbus & glib mainloop
        dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
        self.mainloop = gobject.MainLoop()
        self.bus = dbus.SystemBus()

        # check if there's already something owning our bus name org.freesmartphone.frameworkd
        if "%s.frameworkd" % DBUS_BUS_NAME_PREFIX in self.bus.list_names():
            logger.error( "dbus bus name org.freesmartphone.frameworkd already claimed. Exiting." )
            sys.exit( -1 )

        self._subsystems = {}
        self.busnames = []
        # FIXME remove hardcoded controller knowledge from objects
        self.config = config

        # call me when idle and in mainloop
        gobject.idle_add( self.idle )

        self._configureLoggers()
        self._handleOverrides()

        self._subsystems["frameworkd"] = subsystem.Framework( self.bus, path, self )
        Controller.objects.update( self._subsystems["frameworkd"].objects() )

        systemstolaunch = self.options.values.subsystems.split( ',' )

        # add internal subsystems
        subsystems = [ entry for entry in os.listdir( path )
                       if os.path.isdir( "%s/%s" % ( path, entry ) ) ]

        # add external subsystems
        for section in config.sections():
            external = config.getValue( section, "external", "" )
            if external and ( external not in subsystems ):
                subsystems.append( section )

        # walk and launch subsystems
        for s in subsystems:
            disable = config.getBool( s, "disable", False )
            external = config.getValue( s, "external", "" )
            if disable:
                logger.info( "skipping subsystem %s as requested via config file." % s )
                continue
            if systemstolaunch != [""]:
                if s not in systemstolaunch:
                    logger.info( "skipping subsystem %s as requested via command line" % s )
                    continue
            if external:
                logger.info( "launching external subsystem %s" % s )
                self._subsystems[s] = subsystem.External( s, external, self )
            else:
                logger.info( "launching internal subsystem %s" % s )
                self._subsystems[s] = subsystem.Subsystem( s, self.bus, path, self )
            Controller.objects.update( self._subsystems[s].objects() )

        # do we have any subsystems left?
        if len( self._subsystems ) == 1: # no additional subsystems could be loaded
            logger.error( "can't launch without at least one subsystem. Exiting." )
            sys.exit( -1 )

    def launch( self ):
        if self.options.values.daemonize:
            self.start() # daemonize, then run self.run()
        else:
            self.run()

    def subsystems( self ):
        return self._subsystems

    def idle( self ):
        logger.info( "================== mainloop   entered ===================" )
        logger.info( "startup time was %.2f seconds" % ( time.time() - self.launchTime ) )
        gobject.timeout_add_seconds( 1*60, self.timeout )
        return False # mainloop: don't call me again

    def timeout( self ):
        """
        Regular timeout.
        """
        # FIXME add self-monitoring and self-healing ;)
        logger.debug( "alive and kicking" )
        return True # mainloop: call me again

    def run( self ):
        """
        Run the mainloop.

        Called after daemonizing, or (in debug mode), from Controller.launch()
        """
        self.mainloop.run()

    def shutdown( self ):
        """
        Quit the mainloop.
        """
        logger.info( "shutting down..." )
        for subsystem in self._subsystems.values():
            subsystem.shutdown()
        self.mainloop.quit()

    #
    # private API
    #
    def _configureLoggers( self ):
        # configure all loggers, default being INFO
        for section in config.sections():
            loglevel = loggingmap.get( config.getValue( section, "log_level", debug ) )
            logger.debug( "setting logger for %s to %s" % ( section, loglevel ) )
            logging.getLogger( section ).setLevel( loglevel )

    def _handleOverrides( self ):
        for override in self.options.values.overrides:
            try:
                left, value = override.split( '=', 1 )
                section, key = left.split( '.', 1 )
            except ValueError:
                self.options.error( "Wrong format for override values" )
            if not config.has_section( section ):
                config.add_section( section )
            config.set( section, key, value )

#----------------------------------------------------------------------------#
if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

