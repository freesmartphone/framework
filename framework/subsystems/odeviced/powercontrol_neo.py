#!/usr/bin/env python
"""
Open Device Daemon - A plugin for Neo 1973 and Neo FreeRunner specific power controls

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: odeviced
Module: powercontrol_neo
"""

MODULE_NAME = "odeviced.powercontrol_neo"
__version__ = "0.7.0"

from helpers import readFromFile, writeToFile
from powercontrol import GenericPowerControl, ResourceAwarePowerControl

import os, sys

import logging
logger = logging.getLogger( MODULE_NAME )

try:
    import wireless
except ImportError:
    wireless = None
    logger.error( "wireless module not available" )

#----------------------------------------------------------------------------#
class NeoBluetoothPowerControl( ResourceAwarePowerControl ):
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        super( NeoBluetoothPowerControl, self ).__init__( bus, "Bluetooth", node )
        self.powernode = "%s/%s" % ( self.node, "power_on" )
        self.resetnode = "%s/%s" % ( self.node, "reset" )

    def setPower( self, power ):
        ResourceAwarePowerControl.setPower( self, power )
        # Neo1973 Bluetooth needs special reset handling after touching power
        if power:
            writeToFile( self.resetnode, "1" )
            writeToFile( self.resetnode, "0" )
        else:
            writeToFile( self.resetnode, "1" )

#----------------------------------------------------------------------------#
class NeoUsbHostPowerControl( ResourceAwarePowerControl ):
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        super( NeoUsbHostPowerControl, self ).__init__( bus, "UsbHost", node )
        # node to provide 5V/100mA to USB gadgets, only present on Neo FreeRunner
        self.powernode = "/sys/devices/platform/neo1973-pm-host.0/hostmode"
        # mode switching
        self.modenode = "/sys/devices/platform/s3c2410-ohci/usb_mode"

    def setPower( self, power ):
        if power:
            writeToFile( self.modenode, "host" )
        else:
            writeToFile( self.modenode, "device" )
        GenericPowerControl.setPower( self, power )

#----------------------------------------------------------------------------#
class NeoWifiPowerControl( ResourceAwarePowerControl ):
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        super( NeoWifiPowerControl, self ).__init__( bus, "WiFi", node )

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
        if walk.lookForUSB and "s3c2410-ohci" in fnames: # works both for 1973 and FreeRunner
            objects.append( NeoUsbHostPowerControl( bus, "%s/%s" % ( dirname, "neo1973-pm-host.0" ) ) )
            walk.lookForUSB = False # only have one USB host

    objects = []
    # scan for device nodes
    devicespath = "/sys/devices/platform"
    walk.lookForBT = True
    walk.lookForUSB = True
    os.path.walk( devicespath, walk, objects )

    # check for network interfaces
    if ( wireless is not None ) and "eth0" in os.listdir( "/sys/class/net"):
        objects.append( NeoWifiPowerControl( bus, "/sys/class/net/eth0" ) )

    return objects

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    pass
