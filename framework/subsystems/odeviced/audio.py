#!/usr/bin/env python
"""
Open Device Daemon - A plugin for audio device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.3.0"

from framework.patterns import asyncworker
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName

import gst
import gobject
import dbus.service
import sys, os, time, struct, subprocess

import logging
logger = logging.getLogger( "odeviced.audio" )

#----------------------------------------------------------------------------#
class UnknownFormat( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.UnknownFormat"

#----------------------------------------------------------------------------#
class PlayerError( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.PlayerError"

#----------------------------------------------------------------------------#
class NotPlaying( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.NotPlaying"

#----------------------------------------------------------------------------#
class AlreadyPlaying( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.AlreadyPlaying"

#----------------------------------------------------------------------------#
class InvalidScenario( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.InvalidScenario"

#----------------------------------------------------------------------------#
class DeviceFailed( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Audio.DeviceFailed"

#----------------------------------------------------------------------------#
class Player( asyncworker.AsyncWorker ):
#----------------------------------------------------------------------------#
    """
    Base class implementing common logic for all Players.
    """

    def __init__( self, dbus_object ):
        asyncworker.AsyncWorker.__init__( self )
        self._object = dbus_object

    def enqueueTask( self, ok_cb, error_cb, task, *args ):
        self.enqueue( ok_cb, error_cb, task, args )

    def task_play( self, ok_cb, error_cb, name, repeat ):
        ok_cb()

    def task_stop( self, ok_cb, error_cb, name ):
        ok_cb()

    def task_panic( self, ok_cb, error_cb ):
        ok_cb()

#----------------------------------------------------------------------------#
class NullPlayer( Player ):
#----------------------------------------------------------------------------#
    """
    A dummy player, useful e.g. if no audio subsystem is available.
    """
    pass

#----------------------------------------------------------------------------#
class GStreamerPlayer( Player ):
#----------------------------------------------------------------------------#
    """
    A Gstreamer based Player.
    """

    decoderMap = { \
        "sid": "siddec",
        "mod": "modplug",
        "mp3": "mad" \
        }

    def __init__( self, *args, **kwargs ):
        Player.__init__( self, *args, **kwargs )
        self.pipelines = {}


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
class AlsaScenarios( object ):
#----------------------------------------------------------------------------#
    """
    Controls alsa audio scenarios.
    """
    def __init__( self, dbus_object, statedir ):
        self._object = dbus_object
        self._statedir = statedir
        self._statenames = None
        # FIXME set default profile (from configuration)
        self._current = "unknown"

    def getScenario( self ):
        return self._current

    def storeScenario( self, scenario ):
        statename = "%s/%s.state" % ( self._statedir, scenario )
        result = subprocess.call( [ "alsactl", "-f", statename, "store" ] )
        if result != 0:
            logger.error( "can't store alsa scenario to %s" % statename )
            return False
        else:
            # reload scenarios next time
            self._statenames = None
            return True

    def getAvailableScenarios( self ):
        # FIXME might check timestamp or use inotify
        if self._statenames is None:
            try:
                files = os.listdir( self._statedir )
            except OSError:
                logger.warning( "no state files in %s found" % self._statedir )
                self._statenames = []
            else:
                self._statenames = [ state[:-6] for state in files if state.endswith( ".state" ) ]
        return self._statenames

    def setScenario( self, scenario ):
        if not scenario in self.getAvailableScenarios():
            return False
        statename = "%s/%s.state" % ( self._statedir, scenario )
        result = subprocess.call( [ "alsactl", "-f", statename, "restore" ] )
        if result == 0:
            self._current = scenario
            self._object.Scenario( scenario, "user" )
            return True
        else:
            logger.error( "can't set alsa scenario from %s" % statename )
            return False

    def hasScenario( self, scenario ):
        return scenario in self.getAvailableScenarios()

#----------------------------------------------------------------------------#
class Audio( dbus.service.Object ):
#----------------------------------------------------------------------------#
    """
    A Dbus Object implementing org.freesmartphone.Device.Audio
    """
    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Audio"

    def __init__( self, bus, config, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Audio"
        dbus.service.Object.__init__( self, bus, self.path )
        self.config = config
        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        # FIXME make it configurable or autodetect which player is to be used
        self.player = GStreamerPlayer( self )
        # FIXME gather scenario path from configuration
        self.scenario = AlsaScenarios( self, "/usr/share/openmoko/scenarios" )

    #
    # dbus info methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetInfo( self, dbus_ok, dbus_error ):
        dbus_ok( self.player.__class__.__name__ )

    #
    # dbus sound methods
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
    # dbus scenario methods
    #
    @dbus.service.method( DBUS_INTERFACE, "", "as",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAvailableScenarios( self, dbus_ok, dbus_error ):
        dbus_ok( self.scenario.getAvailableScenarios() )

    @dbus.service.method( DBUS_INTERFACE, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetScenario( self, dbus_ok, dbus_error ):
        dbus_ok( self.scenario.getScenario() )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetScenario( self, name, dbus_ok, dbus_error ):
        if not self.scenario.hasScenario( name ):
            dbus_error( InvalidScenario( "available scenarios are: %s" % self.scenario.getAvailableScenarios() ) )
        else:
            if self.scenario.setScenario( name ):
                dbus_ok()
            else:
                dbus_error( DeviceFailed( "unknown error while setting scenario" ) )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StoreScenario( self, name, dbus_ok, dbus_error ):
        if self.scenario.storeScenario( name ):
            dbus_ok()
        else:
            dbus_error( DeviceFailed( "unknown error while storing scenario" ) )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "ssa{sv}" )
    def SoundStatus( self, name, status, properties ):
        logger.info( "sound status %s %s %s" % ( name, status, properties ) )

    @dbus.service.signal( DBUS_INTERFACE, "ss" )
    def Scenario( self, scenario, reason ):
        logger.info( "sound scenario %s %s" % ( scenario, reason ) )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Instanciate plugins"""

    return [ Audio( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
