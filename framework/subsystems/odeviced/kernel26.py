#!/usr/bin/env python
"""
Open Device Daemon - A plugin for Kernel 2.6 based class interfaces

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

MODULE_NAME = "odeviced.kernel26"
__version__ = "0.9.9.9"

from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
from framework.config import config
from framework.patterns.kobject import KObjectDispatcher
from framework.patterns.null import Null

import dbus.service
import gobject
import os, time, sys, fcntl
import calendar

import logging
logger = logging.getLogger( MODULE_NAME )

try:
    import pyrtc
except ImportError:
    logger.error( "pyrtc not present. Can not operate real time clock" )

FBIOBLANK = 0x4611
FB_BLANK_UNBLANK = 0
FB_BLANK_POWERDOWN = 4

#----------------------------------------------------------------------------#
class UnsupportedTrigger( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Display.UnsupportedTrigger"

#----------------------------------------------------------------------------#
class InvalidParameter( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.InvalidParameter"

#----------------------------------------------------------------------------#
class Display( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Display
    using the kernel 2.6 backlight class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Display"
    SUPPORTS_MULTIPLE_OBJECT_PATHS = True
    OBJECT_PATH_COUNTER = 0

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Display/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        self.max = int( readFromFile( "%s/max_brightness" % self.node ) )
        self.current = int( readFromFile( "%s/actual_brightness" % self.node ) )
        logger.debug( "current brightness %d, max brightness %d" % ( self.current, self.max ) )
        self.fbblank = config.getBool( MODULE_NAME, "fb_blank", True )
        logger.info( "framebuffer blanking %s" % ( "enabled" if self.fbblank else "disabled" ) )
        # also register object under an incremental path
        self.path2 = DBUS_PATH_PREFIX + "/Display/%d" % self.__class__.OBJECT_PATH_COUNTER
        self.add_to_connection( self._connection, self.path2  )
        self.__class__.OBJECT_PATH_COUNTER += 1

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
        if not self.fbblank:
            return
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
        # initial status = off
        self.SetBrightness( 0 )
        # store available triggers for later
        self.triggers = readFromFile( "%s/trigger" % self.node ).split()
        logger.debug( "available triggers %s" % self.triggers )

    def shutdown( self ):
        """
        Called upon subsystem shutdown.
        """
        self.SetBrightness( 0 )

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
        # validate parameters
        if "timer" not in self.triggers:
            raise UnsupportedTrigger( "Timer trigger not available. Available triggers are %s" % self.triggers )
        # do it
        else:
            writeToFile( "%s/trigger" % self.node, "timer" )
            writeToFile( "%s/delay_on" % self.node, str( abs( delay_on ) ) )
            writeToFile( "%s/delay_off" % self.node, str( abs( delay_off ) ) )

    @dbus.service.method( DBUS_INTERFACE, "iii", "" )
    def BlinkSeconds( self, seconds, delay_on, delay_off ):
        # define stop function
        def stopIt( self=self ):
            self.SetBrightness( 0 )
            return False # remove timer, don't call again
        # start
        self.SetBlinking( delay_on, delay_off )
        gobject.timeout_add_seconds( seconds, stopIt )

    @dbus.service.method( DBUS_INTERFACE, "ss", "" )
    def SetNetworking( self, interface, mode ):
        # validate parameters
        if "netdev" not in self.triggers:
            raise UnsupportedTrigger( "Netdev trigger not available. Available triggers are %s" % self.triggers )
        interfaces = os.listdir( "/sys/class/net" )
        if interface not in interfaces:
            raise InvalidParameter( "Interface %s not known. Available interfaces are %s" % ( interface, interfaces ) )
        modes = mode.strip().split()
        for m in modes:
            if m not in "link rx tx".split():
                raise InvalidParameter( "Mode element %s not known. Available elements are 'link rx tx'" % m )
        # do it
        writeToFile( "%s/trigger" % self.node, "netdev" )
        writeToFile( "%s/device_name" % self.node, str( interface.strip() ) )
        writeToFile( "%s/mode" % self.node, str( mode.strip() ) )

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

        self.powerStatus = "unknown"
        self.online = False
        self.capacity = -1
        self.type_ = readFromFile( "%s/type" % self.node ).lower()
        self.isBattery = ( self.type_ == "battery" )

        # get polling-free battery notifications via kobject/uevent
        if self.isBattery:
            KObjectDispatcher.addMatch( "change", "/class/power_supply/%s" % node.split('/')[-1], self.handlePropertyChange )
            capacityCheckTimeout = config.getInt( MODULE_NAME, "capacity_check_timeout", 60*5 )
            self.capacityWatch = gobject.timeout_add_seconds( capacityCheckTimeout, self.onCapacityCheck )
            # FIXME should this rather be handled globally (controller issuing a coldstart on every subsystem)? Yes!
            gobject.idle_add( self.onColdstart )

    def isPresent( self ):
        toRead = "%s/present" if self.isBattery else "%s/online"
        present = readFromFile( toRead % self.node )
        return ( present == "1" )

    def theType( self ):
        return readFromFile( "%s/type" % self.node )

    def onColdstart( self ):
        data = readFromFile( "%s/uevent" % self.node )
        parts = data.split( '\n' )
        d = dict( [ x.split('=') for x in parts if '=' in x ] )
        self.handlePropertyChange( "coldplug", "<this-battery>", **d )
        return False # mainloop: don't call me again

    def readCapacity( self ):
        if not self.isBattery:
            return 100
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
            logger.warning( "Power supply %s has been removed. On AC.", self )
            self.sendPowerStatusIfChanged( "ac" )
            return True # call me again
        capacity = self.readCapacity()
        self.sendCapacityIfChanged( capacity )
        if self.isPresent():
            if capacity > 98: # older batteries will never reach 100
                self.sendPowerStatusIfChanged( "full" )
        else: # offline
            if capacity <= 5:
                self.sendPowerStatusIfChanged( "empty" )
            elif capacity <= 10:
                self.sendPowerStatusIfChanged( "critical" )
        return True # call me again

    def handlePropertyChange( self, action, path, **properties ):
        if not self.isPresent():
            return False # don't call me again
        logger.debug( "got property action '%s' from uevent for path '%s': %s" % ( action, path, properties ) )
        try:
            self.online = ( properties["POWER_SUPPLY_ONLINE"] == '1' )
        except KeyError:
            pass
        try:
            powerStatus = properties["POWER_SUPPLY_STATUS"].lower()
        except KeyError:
            pass
        else:
            # NOTE1: On some devices, peripherals are connected directly to the battery, which means
            # they can _not_ drag power from USB. Hence, the battery needs to be recharged frequently,
            # even while it is full. To cover up for this, we do not send 'charging' if the last status was
            # full.
            if powerStatus == "charging" and self.powerStatus == "full":
                logger.info( "Charging has been restarted, although power is still full. Ignoring" )
            else:
                # NOTE2: "Not Charging" is an interesting state which can have two reasons:
                # 1.) The charger has been physically inserted but the device has not yet enumerated on USB.
                # 2.) The battery has been fully charged and we're now just grabbing power from the charger.
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

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetType( self ):
        return self.theType()

    # FIXME: we might want to remove that -- anyone really interested should rather walk through the sysfs path
    @dbus.service.method( DBUS_INTERFACE, "", "a{sv}" )
    def GetInfo( self ):
        # AC/BATs differ in lots of nodes. Do we want additional methods for present / online ?
        keys = [ key for key in os.listdir( self.node ) if key != "uevent" if os.path.isfile( "%s/%s" % ( self.node, key ) ) ]
        dict = {}
        for key in keys:
            dict[key] = readFromFile( "%s/%s" % ( self.node, key ) )
        return dict

    @dbus.service.method( DBUS_INTERFACE, "", "b" )
    def IsPresent( self ):
        return self.isPresent()

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetCapacity( self ):
        if self.capacity == -1:
            self.onCapacityCheck()
        return self.capacity

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetPowerStatus( self ):
        return self.powerStatus

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
class RealtimeClock( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.RealtimeClock
    using the kernel 2.6 rtc class device"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".RealtimeClock"
    SUPPORTS_MULTIPLE_OBJECT_PATHS = True
    OBJECT_PATH_COUNTER = 0

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/RTC/%s" % cleanObjectName( node.split('/')[-1] )
        dbus.service.Object.__init__( self, bus, self.path )
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        self.node = node
        # also register object under an incremental path
        self.path2 = DBUS_PATH_PREFIX + "/RTC/%d" % self.__class__.OBJECT_PATH_COUNTER
        self.add_to_connection( self._connection, self.path2  )
        self.__class__.OBJECT_PATH_COUNTER += 1

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetName( self ):
        return self.node.split("/")[-1]

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetCurrentTime( self ):
        """Return seconds since epoch (UTC)"""
        return int( readFromFile( "%s/since_epoch" % self.node ) )

    @dbus.service.method( DBUS_INTERFACE, "i", "" )
    def SetCurrentTime( self, t ):
        """Set time by seconds since epoch (UTC)"""
        pyrtc.rtcSetTime( time.gmtime( t ) )

    @dbus.service.signal( DBUS_INTERFACE, "i" )
    def WakeupTimeChanged ( self, t ):
        pass

    @dbus.service.method( DBUS_INTERFACE, "", "i" )
    def GetWakeupTime( self ):
        """Return wakeup time in seconds since epoch (UTC) if a wakeup
        time has been set. Return 0, otherwise."""
        # the wakealarm attribute is not always present
        result = pyrtc.rtcReadAlarm()
        if result is None:
            logger.error( "Can't read RTC alarm. Returning 0" )
            result = ( ( False, False ), 0 )
        ( enabled, pending ), t = result
        return 0 if not enabled else calendar.timegm( t )

    @dbus.service.method( DBUS_INTERFACE, "i", "" )
    def SetWakeupTime( self, t ):
        """Set wakeup time in seconds since epoch (UTC). Set 0 to disable."""
        if t == 0:
            pyrtc.rtcDisableAlarm()
        else:
            pyrtc.rtcSetAlarm( time.gmtime( t ) )
        self.WakeupTimeChanged( t )

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

    # scan for power supplies (kernel 2.6.24++)
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
            objects.append( RealtimeClock( bus, index, "%s/%s" % ( rtcpath, node ) ) )

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
        iface = requestInterfaceForObject( DBUS_INTERFACE_PREFIX, RealtimeClock.DBUS_INTERFACE, DBUS_PATH_PREFIX+"/RTC/%s" % i )
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

