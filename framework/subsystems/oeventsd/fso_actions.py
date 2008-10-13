# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: fso_actions

"""

from action import Action, DBusAction
from framework.controller import Controller
from framework.config import installprefix

import dbus
import os, subprocess, shlex

import logging
logger = logging.getLogger('oeventsd')

#============================================================================#
class AudioAction(Action):
#============================================================================#
    """
    A dbus action on the freesmartphone audio device
    """
    def __init__(self, path):
        super(AudioAction, self).__init__()
        self.path = path

    def trigger(self, **kargs):
        DBusAction(
            dbus.SystemBus(),
            'org.freesmartphone.odeviced',
            '/org/freesmartphone/Device/Audio',
            'org.freesmartphone.Device.Audio',
            'PlaySound', self.path).trigger()

    def untrigger(self, **kargs):
        DBusAction(
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
class LedAction(Action):
#============================================================================#
    """
    A dbus action on a LED device
    """
    function_name = 'SetLed'

    def __init__(self, device, action):
        self.device = device
        self.action = action
    def set(self, action):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/LED/%s' % self.device
        interface = 'org.freesmartphone.Device.LED'
        if action == 'light':
            return DBusAction(bus, service, obj, interface, 'SetBrightness', 100).trigger()
        elif action == 'blink':
            return DBusAction(bus, service, obj, interface, 'SetBlinking', 100, 1500).trigger()
        elif action == 'dark':
            return DBusAction(bus, service, obj, interface, 'SetBrightness', 0).trigger()
        else:
            logger.error( "unhandled action '%s' for Led" % action )
    def trigger(self, **kargs):
        # TODO: actually retrieve the current state of the led
        self.backup_action = 'dark'
        self.set(self.action)
    def untrigger(self, **kargs):
        self.set(self.backup_action)
    def __repr__(self):
        return "SetLed(%s, %s)" % (self.device, self.action)

#============================================================================#
class DisplayBrightnessAction(DBusAction):
#============================================================================#
    """
    A dbus action on a Display device
    """
    # FIXME device specific, needs to go away from here / made generic (parametric? just take the first?)
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
    # FIXME device specific, needs to go away from here / made generic (parametric? just take the first?)
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

#=========================================================================#
class RingToneAction(Action):
#=========================================================================#
    function_name = 'RingTone'

    def trigger(self, **kargs):
        logger.info( "RingToneAction play" )
        # We use the global Controller class to directly get the object
        prefs = Controller.object( "/org/freesmartphone/Preferences" )
        if prefs is None:
            logger.error( "preferences not available and no default values defined." )
            return
        phone_prefs = prefs.GetService( "phone" )
        ring_tone = phone_prefs.GetValue( "ring-tone" )
        ring_volume = phone_prefs.GetValue( "ring-volume" )
        self.sound_path = os.path.join( installprefix, "share/sounds/", ring_tone )

        logger.info( "Start ringing : tone=%s, volume=%s", ring_tone, ring_volume )
        # XXX: We don't set the ringing volume.
        #      Here we only disable the ringing action if the volume is 0
        self.audio_action = AudioAction(self.sound_path) if ring_volume else Action()
        self.vibrator_action = VibratorAction()

        self.audio_action.trigger()
        self.vibrator_action.trigger()

    def untrigger(self, **kargs):
        logger.info( "RingToneAction stop" )
        self.audio_action.untrigger()
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
        sound_path = os.path.join( installprefix, "share/sounds/", tone )

        if self.cmd == "play":
            logger.info( "Start ringing : tone=%s, volume=%s", tone, volume )
            AudioAction(sound_path, "play")()
            #VibratorAction( action="start" )()

        elif self.cmd == "stop":
            logger.info( "Stop ringing : tone=%s, volume=%s", tone, volume )
            AudioAction( sound_path, "stop" )()
            #VibratorAction( action="stop" )()
        else:
            logger.error( "Unknown MessageToneAction!" )
            assert False, "unknown message tone action"

    def __repr__(self):
        return "MessageToneAction(%s)" % self.cmd

#=========================================================================#
class CommandAction(Action):
#=========================================================================#
    function_name = 'Command'

    def __init__( self, cmd = 'true' ):
        self.cmd = cmd

    def trigger(self, **kargs):
        logger.info( "CommandAction %s", self.cmd )

        # FIXME check return value
        result = subprocess.call( shlex.split( self.cmd ) )

    def __repr__(self):
        return "CommandAction(%s)" % self.cmd
