#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import config
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import gobject
from config import LOG, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

USE_NEW_GSM = True

if USE_NEW_GSM:
    import objects2 as objects
else:
    import objects

class Controller( object ):

    def __init__( self, modemClass ):
        DBusGMainLoop( set_as_default=True )
        self.mainloop = gobject.MainLoop()
        gobject.idle_add( self.idle )
        gobject.timeout_add( 10000, self.timeout )
        self.bus = dbus.SystemBus()
        self.busname = dbus.service.BusName( config.DBUS_BUS_NAME, self.bus )

        self.objects = {}
        self.objects["device"] = objects.Device( self.bus, modemClass )
        self.objects["server"] = objects.Server( self.bus, self.objects["device"] )

    def idle( self ):
        print( "in-mainloop initializer" )
        return False

    def timeout( self ):
        print( "alive and kicking" )
        return True

    def run( self ):
        self.mainloop.run()

class Provider( object ):
    def __init__( self, status, index, longname, shortname = "" ):
        self.status = status
        self.index = index
        self.longname = longname
        self.shortname = shortname or longname

class Storage( object ):

    def __init__( self ):
        self.providers = []
