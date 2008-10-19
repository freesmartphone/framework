#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: subsystem
"""

MODULE_NAME = "frameworkd.subsystem"
__version__ = "1.0.0"

from .config import config, DBUS_BUS_NAME_PREFIX

import dbus
import os, sys, time

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class Subsystem( object ):
#----------------------------------------------------------------------------#
    """
    Encapsulates a frameworkd subsystem exported via dbus.
    """
    def __init__( self, name, bus, path, controller ):
        logger.debug( "subsystem %s created" % name )
        self.launchTime = time.time()
        self.name = name
        self.bus = bus
        self.path = path
        self.controller = controller
        self._objects = {}
        self.busnames = []

        self.busnames.append( self.tryClaimBusName() )
        self.registerModulesInSubsystem()

        # Clean out any busnames that couldn't be assigned
        self.busnames = [ busname for busname in self.busnames if busname != None ]
        if self.busnames == []:
            logger.warning( "service %s doesn't have any busnames registered" % self.name )
        else:
            logger.debug( "service %s now owning busnames %s" % (self.name, self.busnames) )

        self.launchTime = time.time() - self.launchTime
        logger.info( "subsystem %s took %.2f seconds to startup" % ( self.name, self.launchTime ) )

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
                    disable = config.getBool( "%s.%s" % ( self.name, modulename ), "disable", False )
                    if disable:
                        logger.info( "skipping module %s.%s as requested via config file." % ( self.name, modulename ) )
                        continue
                    module = __import__(
                        name = ".".join( ["framework.subsystems", self.name, modulename] ),
                        fromlist = ["factory"],
                        level = 0
                    )
                except Exception, e:
                    logger.error( "could not import %s: %s" % ( filename, e ) )
                    # This is a little bit ugly, but we need to see the traceback !
                    import traceback
                    import sys
                    traceback.print_exception(*sys.exc_info())
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
                need_busnames = getattr( module, "NEEDS_BUSNAMES" )
                for busname in need_busnames:
                    self.busnames.append( self.tryClaimBusName( busname ) )
            except AttributeError:
                logger.debug( "module %s doesn't need additional busnames" % module )

            try:
                for obj in factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, self.name ), self.controller ):
                    self._objects[obj.path] = obj
            except Exception, e:
                    logger.exception( "factory method not successfully completed for module %s" % module )

    def tryClaimBusName( self, name=None ):
        """
        Claim a dbus bus name.
        """
        if not name:
            name = "%s.%s" % ( DBUS_BUS_NAME_PREFIX, self.name )
        try:
            busname = dbus.service.BusName( name, self.bus )
        except dbus.DBusException:
            logger.warning( "Can't claim bus name '%s', check configuration in /etc/dbus-1/system.d/frameworkd.conf" % name )
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

        if self.busnames is []:
            logger.critical( "can't claim master busname. Exiting" )
            sys.exit( -1 )

    def registerModulesInSubsystem( self ):
        import framework.objectquery
        self.registerObjectsFromModule( framework.objectquery )
