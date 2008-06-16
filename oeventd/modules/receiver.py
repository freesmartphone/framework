#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Event Daemon - Receiver objects

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.0.0"

DBUS_INTERFACE_PREFIX = "org.freesmartphone.Event.Receiver"
DBUS_PATH_PREFIX = "/org/freesmartphone/Event/Receiver"

import dbus.service
import os
import sys
import gst
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from helpers import LOG, readFromFile, writeToFile
from gobject import idle_add

def requestInterfaceForObject( bus, prefix, interface, object ):
    proxy = bus.get_object( prefix, object )
    iface = dbus.Interface( proxy, interface )
    return iface

def printAction( events ):
    print events

def attributeFilter( key, value ):
    def _attributeFilter( event, key=key, value=value):
        return event.attributes.get( key ) == value
    return _attributeFilter

def ledAction( bus, name ):
    def _ledAction( event, bus=bus, name=name ):
        led = requestInterfaceForObject(
            bus,
            "org.freesmartphone.Device",
            "org.freesmartphone.Device.LED",
            "/org/freesmartphone/Device/LED/" + name
        )
        if event:
            led.SetBlinking(300, 700)
            print 'enabling led', name
        else:
            led.SetBrightness(0)
            print 'disabling led', name
    return _ledAction

def joinAnd( a, b ):
    def _joinAnd( event, a=a, b=b ):
        return a( event ) and b( event )
    return _joinAnd

#----------------------------------------------------------------------------#
class Receiver( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Event.Receiver"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX
    INDEX = 0

    def __init__( self, bus, action, filter = None ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/%s" % Receiver.INDEX
        Receiver.INDEX += 1
        self.action = action
        self.filter = filter
        self.active = []
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" %
            ( self.__class__.__name__, self.interface, list( self.locations ) )
        )

    def _matchEvent( self, event ):
        return self.filter is None or self.filter( event )

    def handleEvent( self, event ):
        if self._matchEvent( event ):
            if event not in self.active:
                self.active.append( event )
        else:
            if event in self.active:
                self.active.remove( event )
        self.action( self.active )

    def releaseEvent( self, event ):
        if event in self.active:
            self.active.remove( event )
            self.action( self.active )

#----------------------------------------------------------------------------#
class AudioSetupReceiver( Receiver ):
#----------------------------------------------------------------------------#
    def __init__( self, bus ):
        Receiver.__init__( self, bus, self.action, attributeFilter( "type", "Call" ) )
        self.scenario = None

    def action( self, active ):
        status = [event.attributes.get( "status" ) for event in active]
        if "active" in status or "outgoing" in status:
            scenario = "gsmhandset"
        else:
            scenario = "stereoout"
        if not self.scenario == scenario:
            print 'setting alsa to', scenario
            os.system( "alsactl -f /usr/share/openmoko/scenarios/%s.state restore" % scenario )
            self.scenario = scenario

#----------------------------------------------------------------------------#
class RingReceiver( Receiver ):
#----------------------------------------------------------------------------#
    def __init__( self, bus ):
        Receiver.__init__( self, bus, self.action, attributeFilter( "type", "Call" ) )
        self.ringing = False

    def _onMessage( self, bus, message ):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.ringing = False
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.ringing = False
        else:
            print "GST:MSG", t

    def _play( self ):
        self.player = pipeline = gst.Pipeline( "oeventd-pipeline" )
        filesrc = gst.element_factory_make( "filesrc", "source" )
        pipeline.add( filesrc )
        decoder = gst.element_factory_make( "siddec", "decoder" )
        pipeline.add( decoder )
        sink = gst.element_factory_make( "alsasink", "sink" )
        pipeline.add( sink )
        filesrc.link( decoder )
        decoder.link( sink )
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect( "message", self._onMessage )
        filesrc.set_property( "location", "/usr/share/sounds/Arkanoid_PSID.sid" )
        pipeline.set_state(gst.STATE_PLAYING)
        print 'playing ringtone'
        self.ringing = True

    def _stop( self ):
        self.player.set_state(gst.STATE_NULL)
        del self.player
        self.ringing = False
        print 'stopped ringtone'

    def action( self, active ):
        status = [event.attributes.get( "status" ) for event in active]
        ringing = "incoming" in status
        if not self.ringing == ringing:
            if ringing:
                self._play()
            else:
                self._stop()

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    objects = []

    objects.append( Receiver( controller.bus, printAction ) )

    objects.append( Receiver( controller.bus,
        ledAction( controller.bus, "neo1973_vibrator" ),
        joinAnd(
            attributeFilter( "type", "Call" ),
            attributeFilter( "status", "incoming" )
        )
    ) )

    objects.append( AudioSetupReceiver( controller.bus ) )
    objects.append( RingReceiver( controller.bus ) )

    return objects

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    usage = requestInterfaceForObject( bus, DBUS_INTERFACE_PREFIX, GenericUsageControl.DBUS_INTERFACE, DBUS_PATH_PREFIX )

    print "Found resources:", usage.ListResources()
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Requesting GSM..."
    usage.RequestResource("GSM")
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Releasing GSM..."
    usage.ReleaseResource("GSM")
    print "GSM users list:", usage.GetResourceUsers("GSM")
    print "Disabling GSM..."
    usage.SetResourcePolicy("GSM", "disabled")
    print "Enabling GSM..."
    usage.SetResourcePolicy("GSM", "enabled")
    print "Setting GSM to auto..."
    usage.SetResourcePolicy("GSM", "auto")

