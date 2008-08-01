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

from .config import DBUS_INTERFACE_PREFIX

import dbus

import os, sys, logging

loggingmap = { \
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    }

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

    def __init__( self, bus, controller ):
        self.interface = self.DBUS_INTERFACE_FRAMEWORK_OBJECTS
        self.path = "/org/freesmartphone/Framework"
        dbus.service.Object.__init__( self, bus, self.path )
        self.controller = controller

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK_OBJECTS, "s", "ao" )
    def ListObjectsByInterface( self, interface ):
        if interface == "*":
            return [x for x in self.controller.objects.values()]
        elif interface.endswith( '*' ):
            return [x for x in self.controller.objects.values() if x.interface.startswith( interface[:-1] )]
        else:
            return [x for x in self.controller.objects.values() if x.interface == interface]

    @dbus.service.method( DBUS_INTERFACE_FRAMEWORK, "", "as" )
    def ListDebugLoggers( self ):
        """
        List available debug loggers.
        """
        return logging.root.manager.loggerDict.keys()

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
