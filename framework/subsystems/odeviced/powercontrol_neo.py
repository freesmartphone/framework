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
__version__ = "0.8.0"

from helpers import readFromFile, writeToFile
from powercontrol import GenericPowerControl, ResourceAwarePowerControl

import os, subprocess, sys

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
class NeoBluetoothPowerControl( ResourceAwarePowerControl ):
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        ResourceAwarePowerControl.__init__( self, bus, "Bluetooth", node )
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
class NeoUsbHostPowerControl( GenericPowerControl ):
    # WARNING: If it's a ResourceAwarePowerControl and there is no ousaged
    # running on startup, then it will break USBeth by automagically switching
    # to USB host mode (which may not be what you want...)
#----------------------------------------------------------------------------#
    def __init__( self, bus, node ):
        GenericPowerControl.__init__( self, bus, "UsbHost", node )
        # mode switching
        self.modenode = "%s/%s" % ( node, "usb_mode" )
        # node to provide 5V/100mA to USB gadgets, only present on Neo FreeRunner
        self.powernode = "%s/../neo1973-pm-host.0/hostmode" % node

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
        ResourceAwarePowerControl.__init__( self, bus, "WiFi", node )

    def setPower( self, power ):
        powernode = "bind" if power else "unbind"
        writeToFile( "%s/%s" % ( self.node, powernode ), "s3c2440-sdi" )

    def getPower( self ):
        return "eth0" in os.listdir( "/sys/class/net" )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""
    bus = controller.bus

    DEVICE_DIR = "/sys/bus/platform/devices"
    DRIVER_DIR = "/sys/bus/platform/drivers"

    devices = os.listdir( DEVICE_DIR )
    drivers = os.listdir( DRIVER_DIR )

    objects = []

    if "neo1973-pm-bt.0" in devices:
        objects.append( NeoBluetoothPowerControl( bus, "%s/%s" % ( DEVICE_DIR, "neo1973-pm-bt.0" ) ) )

    if "s3c2410-ohci" in devices:
        objects.append( NeoUsbHostPowerControl( bus, "%s/%s" % ( DEVICE_DIR, "s3c2410-ohci" ) ) )

    if "s3c2440-sdi" in drivers:
        objects.append( NeoWifiPowerControl( bus, "%s/%s" % ( DRIVER_DIR, "s3c2440-sdi" ) ) )

    return objects

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    pass
