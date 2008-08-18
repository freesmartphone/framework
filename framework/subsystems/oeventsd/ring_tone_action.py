# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from action import Action, AudioAction, VibratorAction
import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

# from framework.subsystems.opreferencesd import PreferencesManager
from framework.controller import Controller

class RingToneAction(Action):
    def __init__(self, cmd = 'play'):
        self.cmd = cmd
    def __call__(self, **kargs):
        logger.info("RingToneAction %s", self.cmd)

        # We use the global Controller class to directly get the object
        prefs = Controller.get_object('/org/freesmartphone/Preferences')
        phone_prefs = prefs.GetService('phone')
        ring_tone = phone_prefs.GetValue('ring-tone')
        ring_volume = phone_prefs.GetValue('ring-volume')
        sound_path = os.path.join("/usr/share/sounds/", ring_tone)

        if self.cmd == 'play':
            logger.info("Start ringing : tone=%s, volume=%s", ring_tone, ring_volume)
            AudioAction(sound_path, 'play')()
            VibratorAction(action='start')()
        else:
            logger.info("Stop ringing : tone=%s, volume=%s", ring_tone, ring_volume)
            AudioAction(sound_path, 'stop')()
            VibratorAction(action='stop')()
    def __repr__(self):
        return "RingToneAction(%s)" % self.cmd
