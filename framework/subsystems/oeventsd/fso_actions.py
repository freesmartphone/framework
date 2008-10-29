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

import framework.patterns.tasklet as tasklet

from action import Action, DBusAction
from framework.controller import Controller
from framework.config import installprefix

import dbus
import os, subprocess, shlex

import logging
logger = logging.getLogger('oeventsd')


class SetProfile( Action ):
    function_name = 'SetProfile'
    
    def __init__( self, profile ):
        self.profile = profile
    
    @tasklet.tasklet
    def __trigger( self ):
        # We store the current profile
        # XXX: we should use profile push and pop instead
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
        # TODO: how do we handle the case where we untrigger the action
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
    
    # We need to make DBus calls and wait for the result,
    # So we use a tasklet to avoid blocking the mainloop.
    @tasklet.tasklet
    def __trigger(self):
        logger.info( "RingToneAction play" )

        # We get the 'phone' preferences service and
        # retreive the ring-tone and ring-volume config values
        # We are careful to use 'yield' cause the calls could be blocking.
        prefs = dbus.SystemBus().get_object(
            'org.freesmartphone.opreferencesd',
            '/org/freesmartphone/Preferences'
        )
        prefs = dbus.Interface(prefs, 'org.freesmartphone.Preferences')
        
        phone_prefs = yield tasklet.WaitDBus( prefs.GetService, "phone" )
        phone_prefs = dbus.SystemBus().get_object(
            'org.freesmartphone.opreferencesd',
            phone_prefs
        )
        phone_prefs = dbus.Interface(phone_prefs, 'org.freesmartphone.Preferences.Service')
        
        ring_tone = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-tone" )
        ring_volume = yield tasklet.WaitDBus( phone_prefs.GetValue, "ring-volume" )
        self.sound_path = os.path.join( installprefix, "share/sounds/", ring_tone )

        logger.info( "Start ringing : tone=%s, volume=%s", ring_tone, ring_volume )
        # XXX: We don't set the ringing volume.
        #      Here we only disable the ringing action if the volume is 0
        self.audio_action = AudioAction(self.sound_path) if ring_volume != 0 else None
        self.vibrator_action = VibratorAction()

        if self.audio_action:
            self.audio_action.trigger()
        self.vibrator_action.trigger()

    def trigger(self, **kargs):
        self.audio_action = None
        self.vibrator_action = None
        # Start the tasklet
        self.__trigger().start()
        

    def untrigger(self, **kargs):
        logger.info( "RingToneAction stop" )
        if self.audio_action: self.audio_action.untrigger()
        if self.vibrator_action : self.vibrator_action.untrigger()

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

        # XXX: We don't set the ringing volume.
        #      Here we only disable the audio action if the volume is 0
        self.audio_action = AudioAction(sound_path) if volume != 0 else None
        #self.vibrator_action = VibratorAction()


        if self.cmd == "play":
            logger.info( "Start ringing : tone=%s, volume=%s", tone, volume )
            if self.audio_action:
                self.audio_action.trigger()
            #self.vibrator_action.trigger()

        elif self.cmd == "stop":
            logger.info( "Stop ringing : tone=%s, volume=%s", tone, volume )
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

    def __init__( self, cmd = 'true' ):
        self.cmd = cmd

    def trigger(self, **kargs):
        logger.info( "CommandAction %s", self.cmd )

        # FIXME check return value
        result = subprocess.call( shlex.split( self.cmd ) )

    def __repr__(self):
        return "CommandAction(%s)" % self.cmd

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

