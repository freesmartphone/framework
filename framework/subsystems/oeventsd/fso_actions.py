# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: fso_actions

"""

__VERSION__ = "0.4.3"
MODULE_NAME = "oeventsd"

import framework.patterns.tasklet as tasklet

from action import Action
from action import QueuedDBusAction, DBusAction
from framework.controller import Controller
from framework.config import installprefix

import gobject
import dbus
import os, subprocess, shlex

import logging
logger = logging.getLogger( MODULE_NAME )

#============================================================================#
class SetProfile( Action ):
#============================================================================#
    function_name = 'SetProfile'

    def __init__( self, profile ):
        self.profile = profile

    @tasklet.tasklet
    def __trigger( self ):
        # We store the current profile
        # FIXME: we should use profile push and pop instead
        prefs = dbus.SystemBus().get_object(
            'org.freesmartphone.opreferencesd',
            '/org/freesmartphone/Preferences'
        )
        prefs = dbus.Interface(prefs, 'org.freesmartphone.Preferences')
        self.backup_profile = yield tasklet.WaitDBus( prefs.GetProfile )
        # Then we can set the profile
        yield tasklet.WaitDBus( prefs.SetProfile, self.profile )

    def trigger( self, **kargs ):
        self.__trigger().start()

    def untrigger( self, **kargs ):
        # FIXME: how do we handle the case where we untrigger the action
        #       before we finish the trigger tasklet ?
        SetProfile( self.backup_profile ).trigger()

    def __repr__( self ):
        return "SetProfile(%s)" % self.profile

#============================================================================#
class AudioAction(Action):
#============================================================================#
    """
    A dbus action on the freesmartphone audio device
    """
    def __init__(self, path, loop=0, length=0):
        super(AudioAction, self).__init__()
        self.path = path
        self.loop = loop
        self.length = length

    def trigger(self, **kargs):
        QueuedDBusAction(
            dbus.SystemBus(),
            'org.freesmartphone.odeviced',
            '/org/freesmartphone/Device/Audio',
            'org.freesmartphone.Device.Audio',
            'PlaySound', self.path, self.loop, self.length).trigger()

    def untrigger(self, **kargs):
        QueuedDBusAction(
            dbus.SystemBus(),
            'org.freesmartphone.odeviced',
            '/org/freesmartphone/Device/Audio',
            'org.freesmartphone.Device.Audio',
            'StopSound', self.path).trigger()

#============================================================================#
class SetAudioScenarioAction(DBusAction):
#============================================================================#
    """
    A dbus action on the freesmartphone audio device
    """
    def __init__(self, scenario = None, action = 'set' ):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/Audio'
        interface = 'org.freesmartphone.Device.Audio'
        if action == 'set':
            # FIXME gsmhandset ugly ugly hardcoded
            super(SetAudioScenarioAction, self).__init__(bus, service, obj, interface, "SetScenario", scenario)
        else:
            logger.error( "unhandled action '%s' for Audio scenario" % action )

#============================================================================#
class AudioScenarioAction(Action):
#============================================================================#
    function_name = 'SetScenario'

    def __init__(self, scenario):
        self.scenario = scenario

    def trigger(self, **kargs):
        logger.info("Set Audio Scenario %s", self.scenario)
        # TODO: retreive the current scenario so that we can use it when we reset the scenario
        self.backup_scenario = 'stereoout'
        SetAudioScenarioAction(self.scenario).trigger()

    def untrigger(self, **kargs):
        logger.info("Revert Audio Scenario to %s", self.backup_scenario)
        SetAudioScenarioAction(self.backup_scenario).trigger()

    def __repr__(self):
        return "SetScenario(%s)" % self.scenario

#============================================================================#
class DisplayBrightnessAction(DBusAction):
#============================================================================#
    """
    A dbus action on a Display device
    """
    # FIXME: device specific, needs to go away from here / made generic (parametric? just take the first?)
    function_name = 'SetDisplayBrightness'

    def __init__(self, target, brightness):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/Display/%s' % target
        interface = 'org.freesmartphone.Device.Display'
        super(DisplayBrightnessAction, self).__init__(bus, service, obj, interface, 'SetBrightness', brightness)

#============================================================================#
class VibratorAction(Action):
#============================================================================#
    """
    A dbus action on the Openmoko Neo Vibrator device
    """
    function_name = 'Vibration'
    # FIXME: device specific, needs to go away from here / made generic (parametric? just take the first?)
    def __init__(self, target = 'neo1973_vibrator'):
        self.target = target
    def trigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.odeviced',
                    '/org/freesmartphone/Device/LED/%s' % self.target,
                    'org.freesmartphone.Device.LED',
                    'SetBlinking', 300, 700).trigger()

    def untrigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.odeviced',
                    '/org/freesmartphone/Device/LED/%s' % self.target,
                    'org.freesmartphone.Device.LED',
                    'SetBrightness', 0).trigger()

#============================================================================#
class BTHeadsetPlayingAction(Action):
#============================================================================#
    """
    A dbus action on the Bluetooth Headset API
    """
    function_name = 'BTHeadsetPlaying'
    def __init__(self):
        pass
    def trigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.ophoned',
                    '/org/freesmartphone/Phone',
                    'org.freesmartphone.Phone',
                    'SetBTHeadsetPlaying', True).trigger()

    def untrigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.ophoned',
                    '/org/freesmartphone/Phone',
                    'org.freesmartphone.Phone',
                    'SetBTHeadsetPlaying', False).trigger()

    def __repr__(self):
        return "BTHeadsetPlaying()"

#============================================================================#
class OccupyResourceAction(Action):
#============================================================================#
    function_name = 'OccupyResource'

    def __init__(self, resource):
        self.resource = resource

    def trigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.ousaged',
                    '/org/freesmartphone/Usage',
                    'org.freesmartphone.Usage',
                    'RequestResource', self.resource).trigger()

    def untrigger(self, **kargs):
        DBusAction(dbus.SystemBus(),
                    'org.freesmartphone.ousaged',
                    '/org/freesmartphone/Usage',
                    'org.freesmartphone.Usage',
                    'ReleaseResource', self.resource).trigger()

    def __repr__(self):
        return "OccupyResource(%s)" % ( self.resource )

#=========================================================================#
class RingToneAction(Action):
#=========================================================================#
    function_name = 'RingTone'

    def __init__( self, *args, **kwargs ):
        Action.__init__( self )
        logger.debug( "%s: init" )
        self.audio_action = None
        self.vibrator_action = None
        gobject.idle_add( self.initFromMainloop )

    def initFromMainloop( self ):
        self.__init().start()
        return False # mainloop: don't call me again

    def cbPreferencesServiceNotify( self, key, value ):
        """
        Audio preferences have changed. Reload.
        """
        k = str(key)
        if k == "ring-tone":
            self.ring_tone = value
        elif k == "ring-volume":
            self.ring_volume = value
        elif k == "ring-loop":
            self.ring_loop = value
        elif k == "ring-length":
            self.ring_length = value

        self.sound_path = os.path.join( installprefix, "share/sounds/", self.ring_tone )
        self.audio_action = AudioAction(self.sound_path, self.ring_loop, self.ring_length) if self.ring_volume != 0 else None
        self.vibrator_action = VibratorAction()

        logger.debug( "ring tone action changed: audio=%s, vibrator=%s", self.audio_action, self.vibrator_action )

    @tasklet.tasklet
    def __init(self):
        """
        We need to make DBus calls and wait for the result,
        So we use a tasklet to avoid blocking the mainloop.
        """

        logger.debug( "ring tone action init from mainloop" )
        # We get the 'phone' preferences service and
        # retreive the ring-tone and ring-volume config values
        # We are careful to use 'yield' cause the calls could be blocking.
        try:
            prefs = dbus.SystemBus().get_object( "org.freesmartphone.opreferencesd", "/org/freesmartphone/Preferences" )
            prefs = dbus.Interface( prefs, "org.freesmartphone.Preferences" )
        except dbus.DBusException: # preferences daemon probably not present
            logger.warning( "org.freesmartphone.opreferencesd not present. Can't get ring tones." )
        else:
            phone_prefs = yield tasklet.WaitDBus( prefs.GetService, "phone" )
            phone_prefs = dbus.SystemBus().get_object( "org.freesmartphone.opreferencesd", phone_prefs )
            phone_prefs = dbus.Interface( phone_prefs, "org.freesmartphone.Preferences.Service" )

            # connect to signal for later notifications
            phone_prefs.connect_to_signal( "Notify", self.cbPreferencesServiceNotify )

            # FIXME does that still work if (some of) the entries are missing?
            self.ring_tone = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-tone" )
            self.ring_volume = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-volume" )
            self.ring_loop = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-loop" )
            self.ring_length = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-length" )

            self.sound_path = os.path.join( installprefix, "share/sounds/", self.ring_tone )
            self.audio_action = AudioAction(self.sound_path, self.ring_loop, self.ring_length) if self.ring_volume != 0 else None
            self.vibrator_action = VibratorAction()

        logger.debug( "ring tone action: audio=%s, vibrator=%s", self.audio_action, self.vibrator_action )

    def trigger(self, **kargs):
        logger.info( "RingToneAction play" )
        if self.audio_action:
            self.audio_action.trigger()
        self.vibrator_action.trigger()

    def untrigger(self, **kargs):
        logger.info( "RingToneAction stop" )
        if self.audio_action:
            self.audio_action.untrigger()
        if self.vibrator_action:
            self.vibrator_action.untrigger()

    def __repr__(self):
        return "RingToneAction()"

#=========================================================================#
class MessageToneAction(Action):
#=========================================================================#
    function_name = 'MessageTone'

    def __init__( self, cmd = 'play' ):
        self.cmd = cmd

    def trigger(self, **kargs):
        logger.info( "MessageToneAction %s", self.cmd )

        # We use the global Controller class to directly get the object
        prefs = Controller.object( "/org/freesmartphone/Preferences" )
        if prefs is None:
            logger.error( "preferences not available and no default values defined." )
            return
        phone_prefs = prefs.GetService( "phone" )
        tone = phone_prefs.GetValue( "message-tone" )
        volume = phone_prefs.GetValue( "message-volume" )
        loop = phone_prefs.GetValue( "message-loop" )
        length = phone_prefs.GetValue( "message-length" )
        sound_path = os.path.join( installprefix, "share/sounds/", tone )

        # XXX: We don't set the ringing volume.
        #      Here we only disable the audio action if the volume is 0
        self.audio_action = AudioAction(sound_path, loop, length) if volume != 0 else None
        #self.vibrator_action = VibratorAction()

        if self.cmd == "play":
            logger.info( "Start message tone : tone=%s, volume=%s, loop=%d, length=%d", tone, volume, loop, length )
            if self.audio_action:
                self.audio_action.trigger()
            #self.vibrator_action.trigger()

        elif self.cmd == "stop":
            logger.info( "Stop message tone : tone=%s, volume=%s, loop=%d, length=%d", tone, volume, loop, length )
            if self.audio_action: self.audio_action.untrigger()
            if self.vibrator_action : self.vibrator_action.untrigger()
        else:
            logger.error( "Unknown MessageToneAction!" )
            assert False, "unknown message tone action"

    def __repr__(self):
        return "MessageToneAction(%s)" % self.cmd

#=========================================================================#
class CommandAction(Action):
#=========================================================================#
    function_name = 'Command'

    def __init__( self, cmd = 'true', env = {} ):
        self.cmd = cmd
        self.env = env

    def trigger(self, **kargs):
        logger.info( "CommandAction %s", self.cmd )

        env = {}
        env.update( os.environ )
        env.update( self.env )

        # FIXME if we are interested in tracking the process, then we
        # should use glib's spawn async and add a chile watch
        try:
            subprocess.Popen( shlex.split( self.cmd ), env = env )
        except Exception, e:
            logger.error( "Error while executing external command '%s': %s", self.cmd, e )

    def __repr__(self):
        return "CommandAction(%s, %s)" % ( self.cmd, self.env )

#============================================================================#
class SuspendAction(DBusAction):
#============================================================================#
    """
    A dbus action to supend the device
    """
    function_name = 'Suspend'

    def __init__(self):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.ousaged'
        obj = '/org/freesmartphone/Usage'
        interface = 'org.freesmartphone.Usage'
        super(SuspendAction, self).__init__(bus, service, obj, interface, 'Suspend')

#============================================================================#
class ExternalDBusAction(DBusAction):
#============================================================================#
    function_name = "ExternalDBusAction"

    """
    A flexible dbus action
    """
    def __init__(self, bus, service, obj, interface, method, *args):
        """Create the DBus action

        arguments:
        - bus       the DBus bus name (or a string : 'system' | 'session')
        - service   the DBus name of the service
        - obj       the DBus path of the object
        - interface the Dbus interface of the signal
        - method    the DBus name of the method
        - args      the arguments for the method

        """
        # some arguments checking
        if isinstance(bus, str):
            if bus == 'system':
                bus = dbus.SystemBus()
            elif bus == 'session':
                bus = dbus.SessionBus()
            else:
                raise TypeError("Bad dbus bus : %s" % bus)
        if not obj:
            obj = None

        assert isinstance(service, str), "service is not str"
        assert obj is None or isinstance(obj, str), "obj is not str or None"
        assert isinstance(interface, str), "interface is not str"
        assert isinstance(signal, str), "signal is not str"

        super(ExternalDBusAction, self).__init__(bus, service, obj, interface, method, *args)

    def __repr__( self ):
        return "ExternalDBusAction(bus = %s, service = %s, obj = %s, itf = %s, method = %s)" % (self.bus, self.service, self.obj, self.interface, self.method)

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    pass
