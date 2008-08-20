# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: ring_tone_action

"""

from action import Action, AudioAction, VibratorAction
# from framework.subsystems.opreferencesd import PreferencesManager
from framework.controller import Controller
from framework.config import installprefix

import dbus
import os

import logging
logger = logging.getLogger('oeventsd')


#=========================================================================#
class RingToneAction(Action):
#=========================================================================#
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
        sound_path = os.path.join( installprefix, "/usr/share/sounds/", ring_tone )

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
