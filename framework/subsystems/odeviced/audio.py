#!/usr/bin/env python
"""
Open Device Daemon - A plugin for audio device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: odeviced
Module: audio
"""

MODULE_NAME = "odeviced.audio"
__version__ = "0.5.9.10"

from framework.config import config
from framework.patterns import asyncworker, processguard
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName

APLAY_COMMAND = "/usr/bin/aplay"

import gobject
import dbus.service
import sys, os, time, types, subprocess

import logging
logger = logging.getLogger( "odeviced.audio" )

#----------------------------------------------------------------------------#
class UnknownFormat( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.UnknownFormat"

#----------------------------------------------------------------------------#
class UnsupportedFormat( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.UnsupportedFormat"

#----------------------------------------------------------------------------#
class PlayerError( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.PlayerError"

#----------------------------------------------------------------------------#
class NotPlaying( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.NotPlaying"

#----------------------------------------------------------------------------#
class AlreadyPlaying( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.AlreadyPlaying"

#----------------------------------------------------------------------------#
class ScenarioInvalid( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.ScenarioInvalid"

#----------------------------------------------------------------------------#
class ScenarioStackUnderflow( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.ScenarioStackUnderflow"

#----------------------------------------------------------------------------#
class DeviceFailed( dbus.DBusException ):
#----------------------------------------------------------------------------#
    _dbus_error_name = "org.freesmartphone.Device.Audio.DeviceFailed"

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

    def task_play( self, ok_cb, error_cb, name, loop, length ):
        ok_cb()

    def task_stop( self, ok_cb, error_cb, name ):
        ok_cb()

    def task_panic( self, ok_cb, error_cb ):
        ok_cb()

    @classmethod
    def supportedFormats( cls ):
        return []

#----------------------------------------------------------------------------#
class NullPlayer( Player ):
#----------------------------------------------------------------------------#
    """
    A dummy player, useful e.g. if no audio subsystem is available.
    """
    def task_play( self, ok_cb, error_cb, name, loop, length ):
        logger.info( "NullPlayer [not] playing sound %s" % name )
        ok_cb()

    def task_stop( self, ok_cb, error_cb, name ):
        logger.info( "NullPlayer [not] stopping sound %s" % name )
        ok_cb()

    def task_panic( self, ok_cb, error_cb ):
        logger.info( "NullPlayer [not] stopping all sounds" )
        ok_cb()

#----------------------------------------------------------------------------#
class GStreamerPlayer( Player ):
#----------------------------------------------------------------------------#
    """
    A Gstreamer based Player.
    """

    decoderMap = {}

    @classmethod
    def supportedFormats( cls ):
        try:
            global gst
            import gst as gst
        except ImportError:
            logger.warning( "Could not setup gstreamer player (python-gst not installed?)" )
            return []

        # set up decoder map
        if cls.decoderMap == {}:
            cls._trySetupDecoder( "mod", "modplug" )
            cls._trySetupDecoder( "mp3", "mad" )
            cls._trySetupDecoder( "sid", "siddec" )
            cls._trySetupDecoder( "wav", "wavparse" )
            # ogg w/ integer vorbis decoder, found on embedded systems
            haveit = cls._trySetupDecoder( "ogg", "oggdemux ! ivorbisdec ! audioconvert" )
            if not haveit:
                # ogg w/ floating point vorbis decoder, found on desktop systems
                cls._trySetupDecoder( "ogg", "oggdemux ! vorbisdec ! audioconvert" )
        return cls.decoderMap.keys()

    @classmethod
    def _trySetupDecoder( cls, ext, dec ):
        # FIXME might even save the bin's already, not just the description
        try:
            gst.parse_bin_from_description( dec, 0 )
        except gobject.GError, e:
            logger.warning( "GST can't parse %s; Not adding %s to decoderMap" % ( dec, ext ) )
            return False
        else:
            cls.decoderMap[ext] = dec
            return True

    def __init__( self, *args, **kwargs ):
        Player.__init__( self, *args, **kwargs )
        self.pipelines = {}

    def _onMessage( self, bus, message, name ):
        pipeline, status, loop, length, ok_cb, error_cb = self.pipelines[name]
        logger.debug( "GST message received while file status = %s" % status )
        t = message.type
        if t == gst.MESSAGE_EOS:
            # shall we restart?
            if loop:
                logger.debug( "G: EOS -- restarting stream" )
                pipeline.seek_simple( gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 0 )
            else:
                logger.debug( "G: EOS" )
                self._updateSoundStatus( name, "stopped" )
                pipeline.set_state( gst.STATE_NULL )
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

            if ( previous, current, pending ) == ( gst.STATE_READY, gst.STATE_PAUSED, gst.STATE_PLAYING ):
                self._updateSoundStatus( name, "playing" )
                ok_cb()
                if length:
                    logger.debug( "adding timeout for %s of %d seconds" % ( name, length ) )
                    gobject.timeout_add_seconds( length, self._playTimeoutReached, name )
            elif ( previous, current, pending ) == ( gst.STATE_PLAYING, gst.STATE_PAUSED, gst.STATE_READY ):
                self._updateSoundStatus( name, "stopped" )
                pipeline.set_state( gst.STATE_NULL )
                del self.pipelines[name]
                # ok_cb()
            else: # uninteresting state change
                pass
        else:
            logger.debug( "G: UNHANDLED: %s" % t )

    def _playTimeoutReached( self, name ):
        try:
            pipeline, status, loop, length, ok_cb, error_cb = self.pipelines[name]
        except KeyError: # might have vanished in the meantime?
            logger.warning( "audio pipeline for %s has vanished before timer could fire" % name )
            return False
        previous, current, next = pipeline.get_state()
        logger.debug( "custom player timeout for %s reached, state is %s" % ( name, current ) )
        if loop:
            pipeline.set_state( gst.STATE_NULL )
            del self.pipelines[name]
            self.task_play( lambda: None, lambda foo: None, name, loop, length )
            #pipeline.seek_simple( gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, 0 )
        else:
            self.task_stop( lambda: None, lambda foo: None, name )
        return False # don't call us again, mainloop

    def _updateSoundStatus( self, name, newstatus ):
        pipeline, status, loop, length, ok_cb, error_cb = self.pipelines[name]
        if newstatus != status:
            self.pipelines[name] = pipeline, newstatus, loop, length, ok_cb, error_cb
            self._object.SoundStatus( name, newstatus, {} )

    def task_play( self, ok_cb, error_cb, name, loop, length ):
        if name in self.pipelines:
            error_cb( AlreadyPlaying( name ) )
        else:
            # Split options from filename, these may be useful for advanced
            # settings on MOD and SID files.
            try:
                base, ext = name.rsplit( '.', 1 )
            except ValueError: # no extension provided
                return error_cb( UnknownFormat( "Can't guess format from extension" ) )
            options = ext.split( ';' )
            ext = options.pop( 0 )
            file = ".".join( [ base, ext ] ).replace( ' ', r'\ ' )
            try:
                decoder = GStreamerPlayer.decoderMap[ ext ]
            except KeyError:
                return error_cb( UnknownFormat( "Known formats are %s" % self.decoderMap.keys() ) )
            else:
                if len(options) > 0:
                    decoder = decoder + " " + " ".join( options )
                # parse_launch may burn a few cycles compared to element_factory_make,
                # however it should still be faster than creating the pipeline from
                # individual elements in python, since it's all happening in compiled code
                try:
                    pipeline = gst.parse_launch( 'filesrc location="%s" ! %s ! alsasink' % ( file, decoder ) )
                except gobject.GError, e:
                    logger.exception( "could not instanciate pipeline: %s" % e )
                    return error_cb( PlayerError( "Could not instanciate pipeline due to an internal error." ) )
                else:
                    # everything ok, go play
                    bus = pipeline.get_bus()
                    bus.add_signal_watch()
                    bus.connect( "message", self._onMessage, name )
                    self.pipelines[name] = ( pipeline, "unknown", loop, length, ok_cb, error_cb )
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

#----------------------------------------------------------------------------#
class AlsaPlayer( Player ):
#----------------------------------------------------------------------------#
    """
    An alsa player, useful for wav format, when the latency of the GStreamerPlayer
    is too heavy.
    """
    @classmethod
    def supportedFormats( cls ):
        if os.path.exists( APLAY_COMMAND ):
            return [ "wav" ]
        else:
            return []

    sounds = {}

    def task_play( self, ok_cb, error_cb, name, loop, length ):
        if name in self.sounds:
            error_cb( AlreadyPlaying() )
        else:
            p = processguard.ProcessGuard( [ "/usr/bin/aplay", str(name) ] )
            p.execute( onExit = self._onPlayingFinished )
            self.sounds[name] = p, loop, length
            ok_cb()
            logger.info( "AlsaPlayer playing sound %s" % name )
            self._object.SoundStatus( name, "playing", {} )

    def task_stop( self, ok_cb, error_cb, name ):
        if name not in self.sounds:
            error_cb( NotPlaying() )
        else:
            p, loop, length = self.sounds[name]
            p.shutdown()
            del self.sounds[name]
            ok_cb()
            logger.info( "AlsaPlayer stopped sound %s" % name )
            self._object.SoundStatus( name, "stopped", {} )

    def task_panic( self, ok_cb, error_cb ):
        logger.info( "AlsaPlayer stopping all sounds" )
        for key, value in self.sounds.items():
            p, loop, length = value
            p.shutdown()
            del self.sounds[key]
            self._object.SoundStatus( key, "stopped", {} )
        ok_cb()

    def _onPlayingFinished( self, pid, exitcode, exitsignal ):
        logger.info( "AlsaPlayer %d exited with exitcode %d (signal %d)" % ( pid, exitcode, exitsignal ) )

        normalShutdown = ( exitcode == 0 )

        for key, value in self.sounds.items():
            p, loop, length = value
            if p.hadpid == pid or p.pid == pid:

                if normalShutdown and loop:
                    logger.debug( "AlsaPlayer restarting sound %s due to loop value" % key )
                    p.execute( onExit = self._onPlayingFinished )
                else:
                    del self.sounds[key]
                    self._object.SoundStatus( key, "stopped", {} )

#----------------------------------------------------------------------------#
class AlsaScenarios( object ):
#----------------------------------------------------------------------------#
    """
    Controls alsa audio scenarios.
    """
    def __init__( self, dbus_object, statedir, defaultscene ):
        self._object = dbus_object
        self._statedir = statedir
        self._default = defaultscene
        self._statenames = None
        # FIXME set default profile (from configuration)
        # FIXME should be set when this audio object initializes
        self._current = "unknown"
        self._stack = []
        gobject.idle_add( self._initScenario )
        logger.info( " ::: using alsa scenarios in %s, default = %s" % ( statedir, defaultscene ) )

    def _initScenario( self ):
        # gather default profile from preferences
        if os.path.exists( "%s/%s.state" % ( self._statedir, self._default ) ):
            self.setScenario( self._default )
            logger.info( "default alsa scenario restored" )
        else:
            logger.warning( "default alsa scenario '%s' not found in '%s'. device may start uninitialized" % ( self._default, self._statedir ) )
        return False

    def pushScenario( self, scenario ):
        current = self._current
        if self.setScenario( scenario ):
            self._stack.append( current )
            return True
        else:
            return False

    def pullScenario( self ):
        previous = self._stack.pop()
        result = self.setScenario( previous )
        if result is False:
            return result
        else:
            return previous

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
            # work around ASoC DAPM problem
            if scenario == "gsmbluetooth":
                result += subprocess.call( [ "amixer", "sset", "Capture Left Mixer", "Analogue Mix Right" ] )
                result += subprocess.call( [ "amixer", "sset", "Capture Left Mixer", "Analogue Mix Left" ] )
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

    players = {}

    def __init__( self, bus, index, node ):
        self.interface = self.DBUS_INTERFACE
        self.path = DBUS_PATH_PREFIX + "/Audio"
        dbus.service.Object.__init__( self, bus, self.path )

        for player in ( AlsaPlayer, GStreamerPlayer, ):
            supportedFormats = player.supportedFormats()
            instance = player( self )
            for format in supportedFormats:
                if format not in self.players:
                    self.players[format] = instance

        scenario_dir = config.getValue( MODULE_NAME, "scenario_dir", "/etc/alsa/scenario" )
        default_scenario = config.getValue( MODULE_NAME, "default_scenario", "default" )
        self.scenario = AlsaScenarios( self, scenario_dir, default_scenario )

        logger.info( "%s %s initialized. Serving %s at %s" % ( self.__class__.__name__, __version__, self.interface, self.path ) )
        logger.debug( "^^^ found players for following formats: '%s'" % self.players.keys() )

    def playerForFile( self, name ):
        try:
            base, ext = name.rsplit( '.', 1 )
        except ValueError: # no extension provided
            raise UnknownFormat( "Can't guess format from extension" )
        options = ext.split( ';' )
        ext = options.pop( 0 )

        try:
            player = self.players[ext]
        except KeyError:
            raise UnsupportedFormat( "No player registered for format '%s'" % ext )

        return player

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
    @dbus.service.method( DBUS_INTERFACE, "sii", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PlaySound( self, name, loop, length, dbus_ok, dbus_error ):
        self.playerForFile( name ).enqueueTask( dbus_ok, dbus_error, "play", name, loop, length )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopSound( self, name, dbus_ok, dbus_error ):
        self.playerForFile( name ).enqueueTask( dbus_ok, dbus_error, "stop", name )

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopAllSounds( self, dbus_ok, dbus_error ):
        for player in self.players.values():
            player.enqueueTask( dbus_ok, dbus_error, "panic" )

    #
    # dbus scenario methods
    #

    # FIXME ugly. error handling should be done by the scenario itself

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
            dbus_error( ScenarioInvalid( "available scenarios are: %s" % self.scenario.getAvailableScenarios() ) )
        else:
            if self.scenario.setScenario( name ):
                dbus_ok()
            else:
                dbus_error( DeviceFailed( "unknown error while setting scenario" ) )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PushScenario( self, name, dbus_ok, dbus_error ):
        if not self.scenario.hasScenario( name ):
            dbus_error( ScenarioInvalid( "available scenarios are: %s" % self.scenario.getAvailableScenarios() ) )
        else:
            if self.scenario.pushScenario( name ):
                dbus_ok()
            else:
                dbus_error( DeviceFailed( "unknown error while pushing scenario" ) )

    @dbus.service.method( DBUS_INTERFACE, "", "s",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PullScenario( self, dbus_ok, dbus_error ):
        try:
            previousScenario = self.scenario.pullScenario()
        except IndexError:
            dbus_error( ScenarioStackUnderflow( "forgot to push a scenario?" ) )
        else:
            if previousScenario is False:
                dbus_error( DeviceFailed( "unknown error while pulling scenario" ) )
            else:
                dbus_ok( previousScenario )

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

    return [ Audio( controller.bus, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
