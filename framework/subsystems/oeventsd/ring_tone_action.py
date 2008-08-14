
from action import Action, AudioAction, VibratorAction
import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

from framework.subsystems.opreferencesd import PreferencesManager

class RingToneAction(Action):
    def __init__(self, cmd = 'play'):
        self.cmd = cmd
    def __call__(self, **kargs):
        logger.info("RingToneAction %s", self.cmd)
        
        # First we need to get the ring-tone music :
        # TODO: as soon as we have some sort of global get_object('Preferences')
        #       method we should use it instead of PreferencesManager.singleton
        prefs = PreferencesManager.singleton
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
