#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: subsystem
"""

MODULE_NAME = "frameworkd.subsystem"
__version__ = "1.2.0"

from .config import config, busmap, DBUS_BUS_NAME_PREFIX

from patterns.processguard import ProcessGuard

import dbus
import os, sys, time

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class Subsystem( object ):
#----------------------------------------------------------------------------#
    """
    Encapsulates a frameworkd subsystem exported via dbus.

    Every subsystem has its dedicated dbus bus connection to
    prevent all objects showing up on all bus names.
    """
    def __init__( self, name, bus, path, scantype, controller ):
        logger.debug( "subsystem %s created" % name )
        self.launchTime = time.time()
        self.name = name
        self.bus = dbus.bus.BusConnection( dbus.bus.BUS_SYSTEM )
        busmap[name] = self.bus
        self.path = path
        self.scantype = scantype
        self.controller = controller
        self._objects = {}
        self.busnames = []

        self.launch()

        self.launchTime = time.time() - self.launchTime
        logger.info( "subsystem %s took %.2f seconds to startup" % ( self.name, self.launchTime ) )

    def launch( self ):
        """
        Launch the subsystem.
        """
        self.busnames.append( self.tryClaimBusName() )
        self.registerModulesInSubsystem()

        # Clean out any busnames that couldn't be assigned
        self.busnames = [ busname for busname in self.busnames if busname != None ]
        if self.busnames == []:
            logger.warning( "service %s doesn't have any busnames registered" % self.name )
        else:
            logger.debug( "service %s now owning busnames %s" % (self.name, self.busnames) )

    def shutdown( self ):
        """
        Shutdown the subsystems, giving objects a chance
        to clean up behind them.
        """
        for o in self._objects.values():
            try:
                o.shutdown()
            except AttributeError: # objects do not have to support this method
                pass

    def objects( self ):
        return self._objects

    def findModulesInSubsystem( self ):
        """
        Find modules belonging to this subsystem.
        Depening on the scantype this is either based on the
        available config settings or 'auto', in which case
        the whole subsystem's directory is scanned (slow!)
        """
        if self.scantype == "auto":
            modules = os.listdir( "%s/%s" % ( self.path, self.name ) )
        else:
            modules = [ section for section in config.sections() \
                        if '.' in section \
                        if section.split('.')[0] == self.name ]

        logger.info( "Scanned subsystem via method '%s', result is %s", self.scantype, modules )
        return modules

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
                        name = "%s.%s" % ( self.name, modulename ),
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
                # we used to pass the controller to the individual objects, we no longer do but
                # pass ourself instead
                for obj in factory( "%s.%s" % ( DBUS_BUS_NAME_PREFIX, self.name ), self ):
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
    def __init__( self, bus, path, scantype, controller ):
        Subsystem.__init__( self, "frameworkd", bus, path, scantype, controller )

        if self.busnames is []:
            logger.critical( "can't claim master busname. Exiting" )
            sys.exit( -1 )

    def registerModulesInSubsystem( self ):
        import framework.objectquery
        self.registerObjectsFromModule( framework.objectquery )

#----------------------------------------------------------------------------#
class External( Subsystem ):
#----------------------------------------------------------------------------#
    """
    A Wrapper for an external subsystem.

    An external subsystem is "just" a child process to us.
    """
    def __init__( self, name, path, scantype, controller ):
        self._process = ProcessGuard( path )
        Subsystem.__init__( self, name, None, None, scantype, controller )

    def launch( self ):
        self._process.execute( onExit=self.processExit )

    def processExit( self, pid, exitcode, exitsignal ):
        print "process has exit :/"

    def shutdown( self ):
        self._process.shutdown()
