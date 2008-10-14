#!/usr/bin/env python
"""
Open Device Daemon - A plugin for Kernel 2.6 based class interfaces

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

MODULE_NAME = "odeviced.kernel26"
__version__ = "0.9.5"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
from framework.config import config

import dbus.service

import gobject

import os, time, sys, socket, fcntl
socket.NETLINK_KOBJECT_UEVENT = 15 # not present in earlier versions

import logging
logger = logging.getLogger( MODULE_NAME )

FBIOBLANK = 0x4611
FB_BLANK_UNBLANK = 0
FB_BLANK_POWERDOWN = 4

#----------------------------------------------------------------------------#
class Display( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Display
    using the kernel 2.6 backlight class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Display"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Display/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        self.max = int( readFromFile( "%s/max_brightness" % self.node ) )
        self.current = int( readFromFile( "%s/actual_brightness" % self.node ) )
        logger.debug( "current brightness %d, max brightness %d" % ( self.current, self.max ) )

    def _valueToPercent( self, value ):
        """
        convert device dependent value to percentage
        """
        return int( 100.0 / self.max * int( value ) )

    def _percentToValue( self, percent ):
        """
        convert percentage to device dependent value
        """
        if percent >= 100:
            value = self.max
        elif percent <= 0:
            value = 0
        else:
            value = int( round( percent / 100.0 * self.max ) )
        return value

    def _setFbPower( self, on ):
        """
        set power on current framebuffer device
        """
        try:
            framebuffer = open( "/dev/fb0" )
        except IOError:
            logger.exception( "can't open framebuffer device to issue ioctl" )
        else:
            logger.debug( "issuing ioctl( FBIOBLANK, %s )" % ( "FB_BLANK_UNBLANK" if on else "FB_BLANK_POWERDOWN" ) )
            result = fcntl.ioctl( framebuffer, FBIOBLANK, FB_BLANK_UNBLANK if on else FB_BLANK_POWERDOWN )
            if result != 0:
                logger.warning( "issuing ioctl( FBIOBLANK, %s ) returned error %d", ( "FB_BLANK_UNBLANK" if on else "FB_BLANK_POWERDOWN" ), result )
        return False # don't call me again
    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.node.split("/")[-1]

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetBrightness( self ):
        value = readFromFile( "%s/actual_brightness" % self.node )
        return self._valueToPercent( value )

    @dbus.service.method( DBUS_INTERFACE, "i", "" )
    def SetBrightness( self, brightness ):
        value = self._percentToValue( brightness )
        if self.current != value:
            writeToFile( "%s/brightness" % self.node, str( value ) )
            if self.current == 0: # previously, we were off
                self._setFbPower( True )
            elif value == 0:
                self._setFbPower( False )
            self.current = value

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def GetBacklightPower( self ):
        return readFromFile( "%s/bl_power" % self.node ) == "0"

    @dbus.service.method( DBUS_INTERFACE, "b", "" )
    def SetBacklightPower( self, power ):
        value = 0 if power else 1
        writeToFile( "%s/bl_power" % self.node, str( value ) )

#----------------------------------------------------------------------------#
class LED( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.LED
    using the kernel 2.6 led class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".LED"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/LED/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        self.triggers = readFromFile( "%s/trigger" % self.node ).split()
        logger.debug( "available triggers %s" % self.triggers )

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.node.split("/")[-1]

    @dbus.service.method( DBUS_INTERFACE, "i", "" )
    def SetBrightness( self, brightness ):
        writeToFile( "%s/trigger" % self.node, "none" )
        if brightness >= 100:
            value = 255
        elif brightness <= 0:
            value = 0
        else:
            value = int( round( brightness / 100.0 * 255 ) )
        writeToFile( "%s/brightness" % self.node, str( value ) )

    @dbus.service.method( DBUS_INTERFACE, "ii", "" )
    def SetBlinking( self, delay_on, delay_off ):
        # FIXME: raise exception if blinking is not supported
        # FIXME: do we want to implement it manually in that case?
        #if "trigger" in self.triggers:
            writeToFile( "%s/trigger" % self.node, "timer" )
            writeToFile( "%s/delay_on" % self.node, str( abs( delay_on ) ) )
            writeToFile( "%s/delay_off" % self.node, str( abs( delay_off ) ) )
        #else:
        #    raise Exception

#----------------------------------------------------------------------------#
class PowerSupply( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.PowerSupply
    using the kernel 2.6 power_supply class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerSupply"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/PowerSupply/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node

        self.ueventsock = s = socket.socket( socket.AF_NETLINK, socket.SOCK_DGRAM, socket.NETLINK_KOBJECT_UEVENT )
        s.bind( ( os.getpid(), 1 ) )
        self.ueventsockWatch = gobject.io_add_watch( s.fileno(), gobject.IO_IN, self.onUeventActivity )
        capacityCheckTimeout = config.getInt( MODULE_NAME, "capacity_check_timeout", 60*5 )
        self.capacityWatch = gobject.timeout_add_seconds( capacityCheckTimeout, self.onCapacityCheck )
        gobject.idle_add( self.onColdstart )

        self.powerStatus = "unknown"
        self.online = False
        self.capacity = -1

    def isPresent( self ):
        return not ( readFromFile( "%s/present" % self.node ) != '1' )

    def onUeventActivity( self, source, condition ):
        data = self.ueventsock.recv( 1024 )
        logger.debug( "got data from uevent socket: %s" % repr(data) )
        # split up and check whether this is really for us
        parts = data.split( '\x00' )
        name = parts[0]
        myname = "power_supply/%s" % self.node.split("/")[-1]
        if name.endswith( myname ):
            gobject.idle_add( self.handlePropertyChange, dict( [ x.split('=') for x in parts if '=' in x ] ) )
        return True # call me again

    def onColdstart( self ):
        data = readFromFile( "%s/uevent" % self.node )
        parts = data.split( '\n' )
        gobject.idle_add( self.handlePropertyChange, dict( [ x.split('=') for x in parts if '=' in x ] ) )
        return False # don't call me again

    def readCapacity( self ):
        if not self.isPresent():
            return -1
        data = readFromFile( "%s/capacity" % self.node )
        try:
            capacity = int( data )
        except ValueError:
            energy_full = readFromFile( "%s/energy_full" % self.node )
            energy_now = readFromFile( "%s/energy_now" % self.node )
            if energy_full == "N/A" or energy_now == "N/A":
                return -1
            else:
                return 100 * int(energy_now) / int(energy_full)
        else:
            return capacity

    def onCapacityCheck( self ):
        if not self.isPresent():
            return True # call me again
        capacity = self.readCapacity()
        self.sendCapacityIfChanged( capacity )
        if self.online:
            if capacity > 98:
                self.sendPowerStatusIfChanged( "full" )
        else: # offline
            if capacity <= 5:
                self.sendPowerStatusIfChanged( "empty" )
            elif capacity <= 10:
                self.sendPowerStatusIfChanged( "critical" )
        return True # call me again

    def handlePropertyChange( self, properties ):
        if not self.isPresent():
            return False # don't call me again
        logger.debug( "got property change from uevent socket: %s" % properties )
        try:
            self.online = ( properties["POWER_SUPPLY_ONLINE"] == '1' )
        except KeyError:
            pass
        try:
            powerStatus = properties["POWER_SUPPLY_STATUS"].lower()
        except KeyError:
            pass
        else:
            # FIXME: what should we do with the "Not Charging" state? It seems to be only a temporary state
            # occuring during the time the charger has been physically inserted but not been yet enumerated on USB
            if powerStatus != "not charging":
                self.sendPowerStatusIfChanged( powerStatus )
        return False # don't call me again

    def sendPowerStatusIfChanged( self, powerStatus ):
        if powerStatus != self.powerStatus:
            self.PowerStatus( powerStatus )

    def sendCapacityIfChanged( self, capacity ):
        if capacity != self.capacity:
            self.Capacity( capacity )

    #
    # dbus methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.node.split("/")[-1]

    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetInfo( self ):
        # AC/BATs differ in lots of nodes. Do we want additional methods for present / online ?
        dict = {}
        for key in "capacity current_now energy_full energy_full_design energy_now manufacturer model_name status technology type voltage_min_design voltage_now present online".split():
            dict[key] = readFromFile( "%s/%s" % ( self.node, key ) )
        return dict

    # FIXME deprecated, should be removed
    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetEnergyPercentage( self ):
        if self.capacity == -1:
            self.onCapacityCheck()
        return self.capacity

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetCapacity( self ):
        if self.capacity == -1:
            self.onCapacityCheck()
        return self.capacity

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetPowerStatus( self ):
        return self.powerStatus

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def IsPresent( self ):
        return self.isPresent()

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "s" )
    def PowerStatus( self, status ):
        self.powerStatus = status
        logger.info( "power status now %s" % status )

    @dbus.service.signal( DBUS_INTERFACE, "i" )
    def Capacity( self, percent ):
        self.capacity = percent
        logger.info( "capacity now %d" % percent )

#----------------------------------------------------------------------------#
class PowerSupplyApm( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.PowerSupply
    using the kernel apm or acpi facilities"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".PowerSupply"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/PowerSupply/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node

    def readApm( self ):
        return open( self.node, "r" ).read().strip().split()

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return "APM"

    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetInfo( self ):
        return {}

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def GetOnBattery( self ):
        d, b, f, AC, BAT, flags, percentage, time, units = self.readApm()
        return AC != "0x01"

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetEnergyPercentage( self ):
        d, b, f, AC, BAT, flags, percentage, time, units = self.readApm()
        return int( percentage[:-1] )

#----------------------------------------------------------------------------#
class RealTimeClock( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.RealTimeClock
    using the kernel 2.6 rtc class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".RealTimeClock"

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/RealTimeClock/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.node.split("/")[-1]

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetCurrentTime( self ):
        """Return seconds since epoch (UTC)"""
        return readFromFile( "%s/since_epoch" % self.node )

    @dbus.service.method( DBUS_INTERFACE, "s", "" )
    def SetCurrentTime( self, t ):
        """Set time by seconds since epoch (UTC)"""
        pyrtc.rtcSetTime( time.gmtime( t ) )

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetWakeupTime( self ):
        """Return wakeup time in seconds since epoch (UTC) if a wakeup
        time has been set. Return 0, otherwise."""
        # the wakealarm attribute is not always present
        if os.path.exists( "%s/wakealarm" % self.node ):
            return readFromFile( "%s/wakealarm" % self.node )
        else:
            # use ioctl interface
            try:
                import pyrtc
            except ImportError:
                logger.error( "pyrtc not present. Can not operate real time clock" )
            ( enabled, pending ), t = pyrtc.rtcReadAlarm()
            return "0" if not enabled else str( time.mktime( t ) )

    @dbus.service.method( DBUS_INTERFACE, "s", "" )
    def SetWakeupTime( self, t ):
        """Set wakeup time in seconds since epoch (UTC). Set 0 to disable."""
        if os.path.exists( "%s/wakealarm" % self.node ):
            writeToFile( "%s/wakealarm" % self.node, t )
        else:
            # use ioctl interface
            try:
                import pyrtc
            except ImportError:
                logger.error( "pyrtc not present. Can not operate real time clock" )
            if time == "0":
                pyrtc.rtcDisableAlarm()
            else:
                pyrtc.rtcSetAlarm( time.gmtime( t ) )

    @dbus.service.method( DBUS_INTERFACE, "", "" )
    def Suspend( self ):
        writeToFile( "/sys/power/state", "mem" )

    # add poweroff?

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetWakeupReason( self ):
        # FIXME
        return "unknown"

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""
    bus = controller.bus

    objects = []

    # scan for displays
    backlightpath = "/sys/class/backlight"
    if os.path.exists( backlightpath ):
        for ( index, node ) in enumerate( os.listdir( backlightpath ) ):
            logger.debug( "scanning %s %s", index, node )
            objects.append( Display( bus, index, "%s/%s" % ( backlightpath, node ) ) )

    # scan for leds
    ledpath = "/sys/class/leds"
    if os.path.exists( ledpath ):
        for ( index, node ) in enumerate( os.listdir( ledpath ) ):
            logger.debug( "scanning %s %s", index, node )
            objects.append( LED( bus, index, "%s/%s" % ( ledpath, node ) ) )

    # scan for power supplies (apm first, then power supply [kernel 2.6.24++])
    powerpath = "/proc/apm"
    logger.debug( "scanning %s", powerpath )
    if os.path.exists( powerpath ):
        objects.append( PowerSupplyApm( bus, 0, powerpath ) )

    powerpath = "/sys/class/power_supply"
    if os.path.exists( powerpath ):
        for ( index, node ) in enumerate( os.listdir( powerpath ) ):
            logger.debug( "scanning %s %s", index, node )
            objects.append( PowerSupply( bus, index+1, "%s/%s" % ( powerpath, node ) ) )

    # scan for real time clocks
    rtcpath = "/sys/class/rtc"
    if os.path.exists( rtcpath ):
        for ( index, node ) in enumerate( os.listdir( rtcpath ) ):
            logger.debug( "scanning %s %s", index, node )
            objects.append( RealTimeClock( bus, index, "%s/%s" % ( rtcpath, node ) ) )

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

    display = []
    for i in count():
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, Display.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/Display/%s" % i )
        if iface is not None:
            display.append( iface )
        else:
            break

    if display:
        d = display[0]
        print "name =", d.GetName()
        print "backlight power =", d.GetBacklightPower()
        print "brightness =", d.GetBrightness()
        try:
            d.SetBacklightPower( True )
            d.SetBrightness( 50 )
        except dbus.exceptions.DBusException:
            pass # could be permission denied

    led = []
    for i in count():
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, LED.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/LED/%s" % i )
        if iface is not None:
            led.append( iface )
        else:
            break

    power = []
    for i in count():
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, PowerSupply.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/PowerSupply/%s" % i )
        if iface is not None:
            power.append( iface )
        else:
            break

    rtc = []
    for i in count():
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, RealTimeClock.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/RealTimeClock/%s" % i )
        if iface is not None:
            rtc.append( iface )
        else:
            break

    print "result: ", display, power, led, rtc
    print "found %d displays..." % len( display )
    for o in display: print ">", o.GetName()
    print "found %d leds..." % len( led )
    for o in led: print ">", o.GetName()
    print "found %d power supplies..." % len(power)
    for o in power: print ">", o.GetName()
    print "found %d real time clocks..." % len( rtc )
    for o in rtc: print ">", o.GetName()

