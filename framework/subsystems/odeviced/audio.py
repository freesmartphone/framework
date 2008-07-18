#!/usr/bin/env python
"""
Open Device Daemon - A plugin for input device peripherals

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.1.0"

from dbus import DBusException
import dbus.service
import sys, os, time, struct
from Queue import Queue
from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from gobject import io_add_watch, IO_IN, source_remove, timeout_add, timeout_add_seconds, idle_add
from itertools import count
from helpers import LOG, DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX, readFromFile, writeToFile, cleanObjectName
import ConfigParser
import gst
import gobject

class UnknownFormat( DBusException ):
    _dbus_error_name = "org.freesmartphone.Audio.UnknownFormat"

class Player( object ):
    pass

class GStreamerPlayer( Player ):

    decoderMap = { \
        "sid": "siddec",
        "mod": "modplug",
        "mp3": "mad" \
        }

    def __init__( self, dbus_object ):
        self.pipelines = {}
        self._object = dbus_object
        self.q = Queue()
        self.process_source = None

    def _onMessage( self, bus, message, name ):
        pipeline = self.pipelines[name][0]
        t = message.type
        if t == gst.MESSAGE_EOS:
            print "G: EOS"
            pipeline.set_state(gst.STATE_NULL)

        elif t == gst.MESSAGE_ERROR:
            pipeline.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "G: ERROR", err, debug
            # TODO call error dbus callback

        elif t == gst.MESSAGE_STATE_CHANGED:
            previous, current, pending = message.parse_state_changed()
            print "G: STATE NOW", current
            if current == gst.STATE_PLAYING:
                pass
                # TODO call signal on dbus object
                # TODO call ok callback

    def _processTask( self ):
        if self.q.empty():
            return False # don't call me again
        print "getting task from queue...",
        ok_cb, error_cb, task, args = self.q.get()
        print "got task", task, args
        try:
            method = getattr( self, "task_%s" % task )
        except AttributeError:
            print "unhandled task", task, args
        else:
            method( ok_cb, error_cb, *args )
        return True

    def enqueue( self, ok_cb, error_cb, task, *args ):
        restart = self.q.empty()
        self.q.put( ( ok_cb, error_cb, task, args ) )
        if restart:
            self.process_source = gobject.idle_add( self._processTask )

    def task_play( self, ok_cb, error_cb, name, repeat ):
        pipeline = self.createPipeline( name )
        print pipeline
        if pipeline is None:
            error_cb( UnknownFormat( "known formats are %s" % self.decoderMap.keys() ) )
        else:
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect( "message", self._onMessage, name )
            self.pipelines[name] = ( pipeline, repeat, ok_cb, error_cb )
            pipeline.set_state( gst.STATE_PLAYING )

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

    def stop( self, name, ok_cb, error_cb ):
        try:
            self.pipelines[name].set_state( gst.STATE_NULL )
        except KeyError:
            error_cb( "not found" )
        del self.pipeline
        self.ringing = False

    def stopAll( self ):
        pass

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
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )
        # FIXME make it configurable or autodetect
        self.player = GStreamerPlayer( self )

    #
    # dbus methods
    #

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def PlaySound( self, name, dbus_ok, dbus_error ):
        self.player.enqueue( dbus_ok, dbus_error, "play", name, False )

    @dbus.service.method( DBUS_INTERFACE, "s", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopSound( self, name, dbus_ok, dbus_error ):
        self.player.enqueue( dbus_ok, dbus_error, "stop", name )

    @dbus.service.method( DBUS_INTERFACE, "", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def StopAllSounds( self, dbus_ok, dbus_error ):
        self.player.enqueue( dbus_ok, dbus_error, "panic" )

    #
    # dbus signals
    #
    @dbus.service.signal( DBUS_INTERFACE, "ssi" )
    def SoundStatus( self, name, status, properties ):
        LOG( LOG_INFO, __name__, "event", name, status, properties )

#----------------------------------------------------------------------------#
def factory( prefix, controller ):
#----------------------------------------------------------------------------#
    """Scan for available sysfs nodes and instanciate corresponding
    dbus server objects"""

    return [ Audio( controller.bus, controller.config, 0, "" ) ]

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()
