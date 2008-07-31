#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: subsystem
"""

from .config import config, DBUS_BUS_NAME_PREFIX

import dbus
import os, sys

import logging
logger = logging.getLogger( "frameworkd.subsystem" )

#----------------------------------------------------------------------------#
class Subsystem( object ):
#----------------------------------------------------------------------------#
    """
    Encapsulates a frameworkd subsystem exported via dbus.
    """
    def __init__( self, name, bus, path, controller ):
        logger.debug( "subsystem %s created" % name )
        self.name = name
        self.bus = bus
        self.path = path
        self.controller = controller
        self._objects = {}

        self.busname = self.tryClaimBusName()
        self.registerModulesInSubsystem()

    def objects( self ):
        return self._objects

    def findModulesInSubsystem( self ):
        return os.listdir( "%s/%s" % ( self.path, self.name ) )

    def registerModulesInSubsystem( self ):
        """
        Register all the modules found for one subsystem.
        """
        # walk the modules path and find plugins
        for filename in self.findModulesInSubsystem():
            if filename.endswith( ".py" ): # FIXME: we should look for *.pyc, *.pyo, *.so as well
                try:
                    modulename = filename[:-3]
                    disable = config.getBool( modulename, "disable", False )
                    if disable:
                        logger.info( "skipping module '%s' as requested in config." % ( modulename ) )
                        continue
                    module = __import__(
                        name = ".".join( ["framework.subsystems", self.name, modulename] ),
                        fromlist = ["factory"],
                        level = 0
                    )
                except ImportError, e:
                    logger.error( "could not import %s: %s" % ( filename, e ) )
                except Exception, e:
                    logger.error( "could not import %s: %s" % ( filename, e ) )
                else:
                    self.registerObjectsFromModule( module )

    def registerObjectsFromModule( self, module ):
        """
        Register all the objects given back from the factory method in one plugin (module).
        """
        logger.debug( "...in subsystem %s: found module %s" % ( self.name, module ) )
        try:
            factory = getattr( module, "factory" )
        except AttributeError:
            logger.debug( "no plugin: factory function not found in module %s" % module )
        else:
            try:
                for obj in factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, self.name ), self.controller ):
                    self._objects[obj.path] = obj
            except Exception, e:
                    logger.exception( "factory method not successfully completed for module %s" % module )

    def tryClaimBusName( self ):
        """
        Claim a dbus bus name.
        """
        name = "%s.%s" % ( DBUS_BUS_NAME_PREFIX, self.name )
        try:
            busname = dbus.service.BusName( name, self.bus )
        except dbus.DBusException:
            logger.warning( "Can't claim bus name '%s', check configuration in /etc/dbus-1/system.d/frameworkd.conf -- ignoring subsystem." % name )
            busname = None
        return busname

#----------------------------------------------------------------------------#
class Framework( Subsystem ):
#----------------------------------------------------------------------------#
    """
    The master subsystem.
    """
    def __init__( self, bus, path, controller ):
        Subsystem.__init__( self, "frameworkd", bus, path, controller )

        if self.busname is None:
            logger.critical( "can't claim master busname. Exiting" )
            sys.exit( -1 )

    def registerModulesInSubsystem( self ):
        import framework.objectquery
        self.registerObjectsFromModule( framework.objectquery )
