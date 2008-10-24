#!/usr/bin/env python
"""
Open Device Daemon - A plugin for IBM ACPI specific power controls

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: odeviced
Module: powercontrol_ibm
"""

MODULE_NAME = "odeviced.powercontrol_ibm"
__version__ = "0.0.0"

from helpers import readFromFile, writeToFile
from powercontrol import ResourceAwarePowerControl

import os

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class IbmBluetoothPowerControl( ResourceAwarePowerControl ):
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        ResourceAwarePowerControl.__init__( self, bus, "Bluetooth", node )
        self.powernode = self.node
        self.onValue = "enable"
        self.offValue = "disable"

    def getPower( self ):
        return readFromFile( self.powernode ).startswith( "status:\t\tenabled" )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""
    bus = controller.bus

    def walk( objects, dirname, fnames ):
        if walk.lookForBT and "bluetooth" in fnames:
            objects.append( IbmBluetoothPowerControl( bus, "%s/%s" % ( dirname, "bluetooth" ) ) )
            walk.lookForBT = False # only have one BT interface
#        if walk.lookForGPS and "neo1973-pm-gps.0" in fnames:
#        objects.append( NeoGpsPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-gps.0" ) ) )
#            walk.lookForGPS = False # only have one GPS interface
#        if walk.lookForGSM and "neo1973-pm-gsm.0" in fnames:
#            objects.append( NeoGsmPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-gsm.0" ) ) )
#            walk.lookForGSM = False # only have one GSM modem
#        if walk.lookForUSB and "s3c2410-ohci" in fnames: # works both for 1973 and FreeRunner
#            objects.append( NeoUsbHostPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-host.0" ) ) )
#            walk.lookForUSB = False # only have one USB host

    objects = []
    # scan for device nodes
    devicespath = "/proc/acpi/ibm"
    walk.lookForBT = True
    walk.lookForGPS = True
    walk.lookForGSM = True
    walk.lookForUSB = True
    os.path.walk( devicespath, walk, objects )

#    # check for network interfaces
#    if ( wireless is not None ) and "eth0" in os.listdir( "/sys/class/net"):
#        objects.append( NeoWifiPowerControl( bus, "/sys/class/net/eth0" ) )

    return objects

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
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
