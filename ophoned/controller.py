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
from config import LOG, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
import objects
import signal
import gobject
if not hasattr( gobject, "timeout_add_seconds" ):
    def timeout_add_seconds( seconds, callback ):
        return gobject.timeout_add( seconds*1000, callback )
    gobject.timeout_add_seconds = timeout_add_seconds

#=========================================================================#
class Controller( object ):
#=========================================================================#
    def __init__( self, modemtype=None ):
        DBusGMainLoop( set_as_default=True )
        self.mainloop = gobject.MainLoop()
        gobject.idle_add( self.idle )
        gobject.timeout_add_seconds( 10, self.timeout )
        self.bus = dbus.SystemBus()
        self.busname = dbus.service.BusName( config.DBUS_BUS_NAME, self.bus )
        self.modemtype = modemtype
        self._createObjects()

    def _createObjects( self ):
        self.objects = {}
        self.objects["device"] = objects.Device( self.bus, self.modemtype )
        self.objects["server"] = objects.Server( self.bus, self.objects["device"] )

    def idle( self ):
        print( "ophoned: in mainloop" )
        return False

    def timeout( self ):
        print( "ophoned: alive and kicking, %d channels left to open" % self.objects["device"].counter )
        return True

    def run( self ):
        self.mainloop.run()

    def rerun( self ):
        print( "ophoned: relaunching" )
        reload( objects )
        self.objects["device"].__class__ = objects.Device
        self.objects["server"].__class__ = objects.Server
        self.run()
