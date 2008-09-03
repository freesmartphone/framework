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

import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

#============================================================================#
class AudioAction(DBusAction):
#============================================================================#
    """
    A dbus action on the freesmartphone audio device
    """
    def __init__(self, scenario = None, action = 'play'):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/Audio'
        interface = 'org.freesmartphone.Device.Audio'
        method = 'PlaySound' if action == 'play' else 'StopSound'
        super(AudioAction, self).__init__(bus, service, obj, interface, method, scenario)

#============================================================================#
class PlaySound(AudioAction):
#============================================================================#
    function_name = 'PlaySound'
    def __init__(self, file):
        super(PlaySound, self).__init__(file, 'play')

#============================================================================#
class StopSound(AudioAction):
#============================================================================#
    function_name = 'StopSound'
    def __init__(self, file):
        super(StopSound, self).__init__(file, 'stop')

#============================================================================#
class AudioScenarioAction(DBusAction):
#============================================================================#
    """
    A dbus action on the freesmartphone audio device
    """
    function_name = 'SetScenario'

    def __init__(self, scenario = None, action = 'set' ):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/Audio'
        interface = 'org.freesmartphone.Device.Audio'
        if action == 'set':
            # FIXME gsmhandset ugly ugly hardcoded
            super(AudioScenarioAction, self).__init__(bus, service, obj, interface, "SetScenario", scenario)
        else:
            logger.error( "unhandled action '%s' for Audio scenario" % action )

#============================================================================#
class LedAction(DBusAction):
#============================================================================#
    """
    A dbus action on an Openmoko Neo LED device
    """
    function_name = 'SetLed'

    # FIXME device specific, needs to go away from here
    def __init__(self, device, action):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/LED/%s' % device
        interface = 'org.freesmartphone.Device.LED'
        if action == 'light':
            super(LedAction, self).__init__(bus, service, obj, interface, 'SetBrightness', 100)
        elif action == 'blink':
            super(LedAction, self).__init__(bus, service, obj, interface, 'SetBlinking', 100, 1500)
        elif action == 'dark':
             super(LedAction, self).__init__(bus, service, obj, interface, 'SetBrightness', 0)
        else:
            logger.error( "unhandled action '%s' for Led" % action )

#============================================================================#
class VibratorAction(DBusAction):
#============================================================================#
    """
    A dbus action on the Openmoko Neo Vibrator device
    """
    # FIXME device specific, needs to go away from here
    def __init__(self, target = 'neo1973_vibrator', action = 'start'):
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/LED/%s' % target
        interface = 'org.freesmartphone.Device.LED'
        if action == 'start':
            super(VibratorAction, self).__init__(bus, service, obj, interface, 'SetBlinking', 300, 700)
        else:
            super(VibratorAction, self).__init__(bus, service, obj, interface, 'SetBrightness', 0)

class StartVibrationAction(VibratorAction):
    function_name = 'StartVibration'
    def __init__(self):
        super(StartVibrationAction, self).__init__(action='start')

class StopVibrationAction(VibratorAction):
    function_name = 'StopVibration'
    def __init__(self):
        super(StartVibrationAction, self).__init__(action='stop')

#=========================================================================#
class RingToneAction(Action):
#=========================================================================#
    function_name = 'RingTone'

    def __init__( self, cmd = 'play' ):
        self.cmd = cmd

    def __call__(self, **kargs):
        logger.info( "RingToneAction %s", self.cmd )

        # We use the global Controller class to directly get the object
        prefs = Controller.object( "/org/freesmartphone/Preferences" )
        if prefs is None:
            logger.error( "preferences not available and no default values defined." )
            return
        phone_prefs = prefs.GetService( "phone" )
        ring_tone = phone_prefs.GetValue( "ring-tone" )
        ring_volume = phone_prefs.GetValue( "ring-volume" )
        sound_path = os.path.join( installprefix, "share/sounds/", ring_tone )

        if self.cmd == "play":
            logger.info( "Start ringing : tone=%s, volume=%s", ring_tone, ring_volume )
            AudioAction(sound_path, "play")()
            VibratorAction( action="start" )()

        elif self.cmd == "stop":
            logger.info( "Stop ringing : tone=%s, volume=%s", ring_tone, ring_volume )
            AudioAction( sound_path, "stop" )()
            VibratorAction( action="stop" )()
        else:
            logger.error( "Unknown RingToneAction!" )
            assert False, "unknown ring tone action"

    def __repr__(self):
        return "RingToneAction(%s)" % self.cmd
