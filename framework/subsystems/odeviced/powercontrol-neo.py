#!/usr/bin/env python
"""
Open Device Daemon - A plugin for Neo 1973 and Neo FreeRunner specific power controls

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: odeviced
Module: powercontrol-neo
"""

MODULE_NAME = "odeviced.powercontrol-neo"
__version__ = "0.5.1"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile

import gobject
import dbus.service
import os, sys

import logging
logger = logging.getLogger( MODULE_NAME )

try:
    import wireless
except ImportError:
    wireless = None
    logger.error( "wireless module not available" )

#----------------------------------------------------------------------------#
class GenericPowerControl( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """An abstract Dbus Object implementing
    org.freesmartphone.Device.PowerControl"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, name, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/PowerControl/%s" % name
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        self.name = name
        self.powernode = None
        self.resetnode = None

    #
    # default implementations, feel free to override in descendants
    #
    def getPower( self ):
        return int( readFromFile( self.powernode ) )

    def setPower( self, power ):
        value = "1" if power else "0"
        writeToFile( self.powernode, value )

    def reset( self ):
        writeToFile( self.resetnode, "1" )

    def sendPowerSignal( self, expectedPower ):
        if self.getPower() == expectedPower:
            self.Power( self.name, expectedPower )
        else:
            logger.warning( "%s expected a power change for %s to %s which didn't happen" % ( __name__, self.name, expectedPower ) )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.name

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def GetPower( self ):
        return self.getPower()

    @dbus.service.method( DBUS_INTERFACE, "b", "" )
    def SetPower( self, power ):
        if power != self.getPower():
            self.setPower( power )
            gobject.idle_add( lambda self=self: self.sendPowerSignal( power ) )
        else:
            # FIXME should we issue an error here or just silently ignore?
            pass

    @dbus.service.method( DBUS_INTERFACE, "", "" )
    def Reset( self ):
        self.reset()

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "sb" )
    def Power( self, device, power ):
        logger.info( "%s power for %s changed to %s" % ( __name__, self.name, power ) )

#----------------------------------------------------------------------------#
class NeoBluetoothPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, node ):
        GenericPowerControl.__init__( self, bus, "Bluetooth", node )
        self.powernode = "%s/%s" % ( self.node, "power_on" )
        self.resetnode = "%s/%s" % ( self.node, "reset" )

    def setPower( self, power ):
        GenericPowerControl.setPower( self, power )
        # Neo1973 Bluetooth needs special reset handling after touching power
        if power:
            writeToFile( self.resetnode, "1" )
            writeToFile( self.resetnode, "0" )
        else:
            writeToFile( self.resetnode, "1" )

#----------------------------------------------------------------------------#
class NeoGpsPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, node ):
        GenericPowerControl.__init__( self, bus, "GPS", node )
        self.powernode = "%s/%s" % ( self.node, "pwron" )

#----------------------------------------------------------------------------#
class NeoGsmPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, node ):
        GenericPowerControl.__init__( self, bus, "GSM", node )
        self.powernode = "%s/%s" % ( self.node, "power_on" )
        self.resetnode = "%s/%s" % ( self.node, "reset" )

    #
    # Basic idea for this is:
    # * Check for MUXer presence.
    # ** If present, delegate commands to MUXer
    # ** If not present, just do it yourself
    #

#----------------------------------------------------------------------------#
class NeoWifiPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, node ):
        GenericPowerControl.__init__( self, bus, "WiFi", node )

    def setPower( self, power ):
        wireless.wifiSetOn( "eth0", 1 if power else 0 )

    def getPower( self ):
        return wireless.wifiIsOn( "eth0" )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""
    bus = controller.bus

    def walk( objects, dirname, fnames ):
        if walk.lookForBT and "neo1973-pm-bt.0" in fnames:
            objects.append( NeoBluetoothPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-bt.0" ) ) )
            walk.lookForBT = False # only have one BT interface
        if walk.lookForGPS and "neo1973-pm-gps.0" in fnames:
            objects.append( NeoGpsPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-gps.0" ) ) )
            walk.lookForGPS = False # only have one GPS interface
        if walk.lookForGSM and "neo1973-pm-gsm.0" in fnames:
            objects.append( NeoGsmPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-gsm.0" ) ) )
            walk.lookForGSM = False # only have one GSM modem

    objects = []
    # scan for device nodes
    devicespath = "/sys/devices/platform"
    walk.lookForBT = True
    walk.lookForGPS = True
    walk.lookForGSM = True
    os.path.walk( devicespath, walk, objects )

    # check for network interfaces
    if ( wireless is not None ) and "eth0" in os.listdir( "/sys/class/net"):
        objects.append( NeoWifiPowerControl( bus, "/sys/class/net/eth0" ) )
    return objects

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    from itertools import count

    def requestInterfaceForObject( prefix, interface, object ):
        proxy = bus.get_object( prefix, object )
        #print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
        iface = dbus.Interface(proxy, interface )
        try:
            iface.GetName()
        except dbus.exceptions.DBusException:
            return None
        else:
            return iface

    device = []
    for i in count():
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, GenericPowerControl.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/PowerControl/%s" % i )
        if iface is not None:
            device.append( iface )
        else:
            break

    for d in device:
        print( "found interface for '%s' (power status = %d)" % ( d.GetName(), d.GetPower() ) )
