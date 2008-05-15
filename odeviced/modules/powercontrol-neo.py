#!/usr/bin/env python
"""
Open Device Daemon - A plugin for Neo 1973 and Neo FreeRunner specific power controls

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.5.0"

import dbus.service
import os
import sys
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile
from gobject import idle_add
try:
    import wireless
except ImportError:
    wireless = None
    LOG( LOG_ERR, "wireless module not available" )

#----------------------------------------------------------------------------#
class GenericPowerControl( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """An abstract Dbus Object implementing
    org.freesmartphone.Device.PowerControl"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/PowerControl/%s" % node.split("/")[-1]
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )
        self.node = node
        self.name = None
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
            LOG( LOG_WARNING, __name__, "expected a power change for", self.name, "to", expectedPower, "which didn't happen" )

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
            idle_add( lambda self=self: self.sendPowerSignal( power ) )
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
        LOG( LOG_INFO, __name__, "power for", self.name, "changed to", power )

#----------------------------------------------------------------------------#
class NeoBluetoothPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, index, node ):
        GenericPowerControl.__init__( self, bus, index, node )
        self.name = "Bluetooth"
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

    def __init__( self, bus, index, node ):
        GenericPowerControl.__init__( self, bus, index, node )
        self.name = "GPS"
        self.powernode = "%s/%s" % ( self.node, "pwron" )

#----------------------------------------------------------------------------#
class NeoGsmPowerControl( GenericPowerControl ):
#----------------------------------------------------------------------------#
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerControl"

    def __init__( self, bus, index, node ):
        GenericPowerControl.__init__( self, bus, index, node )
        self.name = "GSM"
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

    def __init__( self, bus, index, node ):
        GenericPowerControl.__init__( self, bus, index, node )
        self.name = "WIFI"

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
        #LOG( LOG_DEBUG, "scanning in", dirname, "found", fnames )
        if walk.lookForBT and "neo1973-pm-bt.0" in fnames:
            objects.append( NeoBluetoothPowerControl( bus, walk.index, "%s/%s" % ( dirname, "neo1973-pm-bt.0" ) ) )
            walk.index += 1
            walk.lookForBT = False # only have one BT interface
        if walk.lookForGPS and "neo1973-pm-gps.0" in fnames:
            objects.append( NeoGpsPowerControl( bus, walk.index, "%s/%s" % ( dirname, "neo1973-pm-gps.0" ) ) )
            walk.index += 1
            walk.lookForGPS = False # only have one GPS interface
        if walk.lookForGSM and "neo1973-pm-gsm.0" in fnames:
            objects.append( NeoGsmPowerControl( bus, walk.index, "%s/%s" % ( dirname, "neo1973-pm-gsm.0" ) ) )
            walk.index += 1
            walk.lookForGSM = False # only have one GSM modem

    objects = []
    # scan for device nodes
    devicespath = "/sys/devices/platform"
    walk.lookForBT = True
    walk.lookForGPS = True
    walk.lookForGSM = True
    walk.index = 0
    os.path.walk( devicespath, walk, objects )

    # check for network interfaces
    if ( wireless is not None ) and "eth0" in os.listdir( "/sys/class/net"):
        objects.append( NeoWifiPowerControl( bus, walk.index, "/sys/class/net/eth0" ) )
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

