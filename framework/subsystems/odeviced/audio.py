#!/usr/bin/env python
"""
Open Device Daemon - A plugin for audio device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.2.0"

from patterns import asyncworker
from dbus import DBusException
import dbus.service
from gobject import io_add_watch, IO_IN, source_remove, timeout_add, timeout_add_seconds, idle_add
from itertools import count
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
import ConfigParser
import gst
import gobject
import sys, os, time, struct

import logging
logger = logging.getLogger( "odeviced.audio" )

#----------------------------------------------------------------------------#
class UnknownFormat( DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.UnknownFormat"

#----------------------------------------------------------------------------#
class PlayerError( DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.PlayerError"

#----------------------------------------------------------------------------#
class NotPlaying( DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.NotPlaying"

#----------------------------------------------------------------------------#
class AlreadyPlaying( DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.AlreadyPlaying"

#----------------------------------------------------------------------------#
class Player( object ):
#----------------------------------------------------------------------------#
    pass

#----------------------------------------------------------------------------#
class GStreamerPlayer( Player, asyncworker.AsyncWorker ):
#----------------------------------------------------------------------------#

    decoderMap = { \
        "sid": "siddec",
        "mod": "modplug",
        "mp3": "mad" \
        }

    def __init__( self, dbus_object ):
        Player.__init__( self )
        asyncworker.AsyncWorker.__init__( self )
        self.pipelines = {}
        self._object = dbus_object


    def _onMessage( self, bus, message, name ):
        pipeline, status, repeat, ok_cb, error_cb = self.pipelines[name]
        t = message.type
        if t == gst.MESSAGE_EOS:
            logger.debug( "G: EOS" )
            pipeline.set_state(gst.STATE_NULL)
            del self.pipelines[name]

        elif t == gst.MESSAGE_ERROR:
            pipeline.set_state(gst.STATE_NULL)
            del self.pipelines[name]
            err, debug = message.parse_error()
            logger.debug( "G: ERROR: %s %s" % ( err, debug ) )
            error_cb( PlayerError( err.message ) )

        elif t == gst.MESSAGE_STATE_CHANGED:
            previous, current, pending = message.parse_state_changed()
            logger.debug( "G: STATE NOW: (%s) -> %s -> (%s)" % ( previous, current, pending ) )
            if previous == gst.STATE_PAUSED and current == gst.STATE_PLAYING:
                self._updateSoundStatus( name, "playing" )
                ok_cb()
            elif previous == gst.STATE_PAUSED and current == gst.STATE_PLAYING:
                self._updateSoundStatus( name, "paused" )
                # ok_cb()
            elif previous == gst.STATE_PAUSED and current == gst.STATE_READY:
                self._updateSoundStatus( name, "stopped" )
                pipeline.set_state( gst.STATE_NULL )
                del self.pipelines[name]
                # ok_cb()

        else:
            logger.debug( "G: UNHANDLED: %s" % t )

    def _updateSoundStatus( self, name, newstatus ):
        pipeline, status, repeat, ok_cb, error_cb = self.pipelines[name]
        if newstatus != status:
            self.pipelines[name] = pipeline, newstatus, repeat, ok_cb, error_cb
            self._object.SoundStatus( name, newstatus, {} )

    def onProcessElement( self, element ):
        logger.debug( "getting task from queue..." )
        ok_cb, error_cb, task, args = element
        logger.debug( "got task: %s %s" % ( task, args ) )
        try:
            method = getattr( self, "task_%s" % task )
        except AttributeError:
            logger.debug( "unhandled task: %s %s" % ( task, args ) )
        else:
            method( ok_cb, error_cb, *args )
        return True

    def enqueueTask( self, ok_cb, error_cb, task, *args ):
        self.enqueue( ok_cb, error_cb, task, args )

    def task_play( self, ok_cb, error_cb, name, repeat ):
        if name in self.pipelines:
            error_cb( AlreadyPlaying( name ) )
        else:
            pipeline = self.createPipeline( name )
            if pipeline is None:
                error_cb( UnknownFormat( "known formats are %s" % self.decoderMap.keys() ) )
            else:
                bus = pipeline.get_bus()
                bus.add_signal_watch()
                bus.connect( "message", self._onMessage, name )
                self.pipelines[name] = ( pipeline, "unknown", repeat, ok_cb, error_cb )
                pipeline.set_state( gst.STATE_PLAYING )

    def task_stop( self, ok_cb, error_cb, name ):
        try:
            pipeline = self.pipelines[name][0]
        except KeyError:
            error_cb( NotPlaying( name ) )
        else:
            pipeline.set_state( gst.STATE_READY )
            ok_cb()

    def task_panic( self, ok_cb, error_cb ):
        for name in self.pipelines:
            self.pipelines[name][0].set_state( gst.STATE_READY )
        ok_cb()

    def createPipeline( self, name ):
        extension = name.split( '.' )[-1]
        pipeline = gst.Pipeline( "name" )
        filesrc = gst.element_factory_make( "filesrc", "source" )
        filesrc.set_property( "location", name )
        pipeline.add( filesrc )
        try:
            decoder = gst.element_factory_make( self.decoderMap[extension], "decoder" )
        except KeyError:
            return None
        else:
            pipeline.add( decoder )
            sink = gst.element_factory_make( "alsasink", "sink" )
            pipeline.add( sink )
            filesrc.link( decoder )
            decoder.link( sink )
            return pipeline

#----------------------------------------------------------------------------#
class Audio( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """A Dbus Object implementing org.freesmartphone.Device.Audio"""
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Audio"

    def __init__( self, bus, config, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Audio"
        dbus.service.Object.__init__( self, bus, self.path )
        self.config = config
        logger.info( "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )
        # FIXME make it configurable or autodetect
        self.player = GStreamerPlayer( self )

    #
    # dbus methods
    #

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PlaySound( self, name, dbus_ok, dbus_error ):
        self.player.enqueueTask( dbus_ok, dbus_error, "play", name, False )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopSound( self, name, dbus_ok, dbus_error ):
        self.player.enqueueTask( dbus_ok, dbus_error, "stop", name )

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopAllSounds( self, dbus_ok, dbus_error ):
        self.player.enqueueTask( dbus_ok, dbus_error, "panic" )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "ssa{sv}" )
    def SoundStatus( self, name, status, properties ):
        logger.info( "%s sound status %s %s %s", __name__, name, status, properties )

    @dbus.service.signal( DBUS_INTERFACE, "ss" )
    def Scenario( self, scenario, reason ):
        logger.info( "%s scenario %s %s", __name__, scenario, reason )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""

    return [ Audio( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
