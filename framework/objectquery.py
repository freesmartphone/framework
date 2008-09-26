#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Device Daemon - Framework Introspection Object

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

__version__ = "0.5.1"

from .introspection import process_introspection_data
from .config import DBUS_INTERFACE_PREFIX
from framework.patterns import tasklet

import dbus, dbus.service

import os, sys, logging, logging.handlers
logger = logging # is this ok or do we need a formal logger for this module as well?

loggingmap = { \
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    }

formatter = logging.Formatter('%(asctime)s %(name)-12s: %(levelname)-8s %(message)s')

#----------------------------------------------------------------------------#
class InvalidLogger( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Framework.InvalidLogger"

#----------------------------------------------------------------------------#
class InvalidLevel( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Framework.InvalidLevel"

#----------------------------------------------------------------------------#
class InvalidTarget( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Framework.InvalidTarget"

#----------------------------------------------------------------------------#
class Objects( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A D-Bus Object implementing org.freesmartphone.Objects"""
    DBUS_INTERFACE_FRAMEWORK = DBUS_INTERFACE_PREFIX + ".Framework"
    DBUS_INTERFACE_FRAMEWORK_OBJECTS = DBUS_INTERFACE_PREFIX + ".Objects"

    InterfaceCache = {}

    def __init__( self, bus, controller ):
        self.interface = self.DBUS_INTERFACE_FRAMEWORK_OBJECTS
        self.path = "/org/freesmartphone/Framework"
        self.bus = bus
        dbus.service.Object.__init__( self, bus, self.path )
        self.controller = controller

    def _getInterfaceForObject( self, object, interface ):
        obj = self.bus.get_object( "org.freesmartphone.frameworkd", object )
        return dbus.Interface( obj, interface )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK_OBJECTS, "s", "ao",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def ListObjectsByInterface( self, interface, dbus_ok, dbus_error ):

        @tasklet.tasklet
        def task( self=self, interface=interface ):
            if interface == "*":
                yield self.controller.objects.keys()
            else:
                objects = []

                for object in self.controller.objects:
                    try:
                        interfaces = Objects.InterfaceCache[object]
                    except KeyError:
                        logger.debug( "introspecting object %s..." % object )
                        introspectionData = yield tasklet.WaitDBus( self._getInterfaceForObject( object, "org.freedesktop.DBus.Introspectable" ).Introspect )
                        interfaces = process_introspection_data( introspectionData )["interfaces"]
                        Objects.InterfaceCache[object] = interfaces

                    logger.debug( "interfaces for object are %s" % interfaces )
                    for iface in interfaces:
                        if interface.endswith( '*' ):
                            if iface.startswith( interface[:-1] ):
                                objects.append( object )
                                break
                        else:
                            if iface == interface:
                                objects.append( object )
                                break

                logger.debug( "introspection fully done, result is %s" % objects )
                yield objects

        task().start_dbus( dbus_ok, dbus_error )

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "", "as" )
    def ListDebugLoggers( self ):
        """
        List available debug loggers.
        """
        return logging.root.manager.loggerDict.keys()

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "", "ss" )
    def GetDebugDestination( self ):
        try:
            handler = logging.root.handlers[0]
        except IndexError:
            handler = logging.StreamHandler()

        if isinstance( handler, logging.StreamHandler ):
            return ( "stderr", "" )
        elif isinstance( handler, logging.handlers.SysLogHandler ):
            return ( "syslog", "" )
        elif isinstance( handler, logging.FileHandler ):
            return ( "file", handler.stream.name )
        else:
            return ( "unknown", "" )

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "ss", "" )
    def SetDebugDestination( self, category, destination ):
        """
        Set the debug destination of logger.
        """
        if category == "stderr":
            handler = logging.StreamHandler()
        elif category == "syslog":
            handler = logging.handlers.SysLogHandler( address = "/dev/log" )
        elif category == "file" and destination != "":
            handler = logging.FileHandler( destination )
        else:
            raise InvalidHandler( "available handlers are: stderr, syslog, file" )

        handler.setFormatter( formatter )
        # yank existing handlers before adding new one
        for h in logging.root.handlers:
            logging.root.removeHandler( h )
        logging.root.addHandler( handler )

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "s", "s" )
    def GetDebugLevel( self, logger ):
        """
        Get the debug level of logger.
        """
        try:
            logger = logging.root.manager.loggerDict[logger]
        except KeyError:
            raise InvalidLogger( "available loggers are: %s" % logging.root.manager.loggerDict.keys() )
        else:
            return logging.getLevelName( logger.level )

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "ss", "" )
    def SetDebugLevel( self, logger, levelname ):
        """
        Set the debug level of logger to levelname.
        """
        try:
            level = loggingmap[levelname]
        except KeyError:
            raise InvalidLevel( "available levels are: %s" % loggingmap.keys() )
        else:
            if logger != "*":
                try:
                    logger = logging.root.manager.loggerDict[logger]
                except KeyError:
                    raise InvalidLogger( "available loggers are: %s" % logging.root.manager.loggerDict.keys() )
                else:
                    logger.setLevel( level )
            else:
                for logger in logging.root.manager.loggerDict.items():
                    logger.setLevel( level )

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "", "as" )
    def ListSubsystems( self ):
        return self.controller.subsystems().keys()

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "s", "as" )
    def ListObjectsInSubsystem( self, subsystem ):
        pass

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    return [ Objects( controller.bus, controller ) ]

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    import dbus
    bus = dbus.SystemBus()

    query = bus.get_object( "org.freesmartphone.frameworkd", "/org/freesmartphone/Framework" )
    objects = query.ListObjectsByInterface( '*',  dbus_interface="org.freesmartphone.Objects" )

    phone = bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
