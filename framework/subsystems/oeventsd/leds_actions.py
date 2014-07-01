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

MODULE_NAME = "oeventsd"
__version__ = "0.5.0"

import dbus

from framework.patterns import dbuscache, tasklet

from action import Action, DBusAction

import logging
logger = logging.getLogger( MODULE_NAME )

#============================================================================#
class Led(object):
#============================================================================#
    """
    Led object
    This class is used to keep track of every "clients" that wants to use the led.
    The current status of the led id the higher level of all the clients,
    the levels being :
    - dark
    - blink
    - light
    """

    # We keep a list of all the leds object maped by device name
    __leds = {}

    def __new__(cls, device):
        """We don't create two leds with the same device""" 
        if device in Led.__leds:
            return Led.__leds[device]
        ret = object.__new__(cls)
        ret.__init(device)
        return ret

    def __repr__(self):
        return self.device

    def __init(self, device):
        self.device = device

        self.interface = dbuscache.dbusInterfaceForObjectWithInterface(
            "org.freesmartphone.odeviced",
            "/org/freesmartphone/Device/LED/%s" % device,
            "org.freesmartphone.Device.LED" )
        self.users = {}

    def on_reply(self, *args):
        # We don't pass the reply to anything
        pass

    def on_error(self, error):
        logger.error("DBus call returned an error")

    def __turn_on(self):
        logger.info("turn led %s on", self)
        self.interface.SetBrightness(100, reply_handler=self.on_reply, error_handler=self.on_error)

    def __turn_off(self):
        logger.info("turn led %s off", self)
        self.interface.SetBrightness(0, reply_handler=self.on_reply, error_handler=self.on_error)

    def __blink(self):
        logger.info("blink led %s", self)
        self.interface.SetBlinking(self.durationOn, self.durationOff, reply_handler=self.on_reply, error_handler=self.on_error)

    def turn_on(self, user):
        self.users[user] = 'on'
        self.__update()

    def turn_off(self, user):
        if user in self.users:
            del self.users[user]
        else:
            logger.warning("try to turn off led %s before having turing it on", self)
        self.__update()

    def blink(self, user, durationOn, durationOff):
        self.users[user] = 'blink'
        self.durationOn = durationOn
        self.durationOff = durationOff
        self.__update()

    def __update(self):
        status = self.users.values()
        logger.debug("led %s status = %s", self, status)
        if 'on' in status:
            self.__turn_on()
        elif 'blink' in status:
            self.__blink()
        else:
            self.__turn_off()

#============================================================================#
class LedAction(Action):
#============================================================================#
    """
    A dbus action on a LED device
    """
    function_name = 'SetLed'

    def __init__(self, device, action, onDuration = 100, offDuration = 1500):
        Action.__init__( self )
        self.led = Led(device)
        self.action = action
        if not action in ['light', 'blink']:
            logger.error("Unhandeled action on led %s : %s", device, action)

    def trigger(self, **kargs):
        if self.action == 'light':
            self.led.turn_on(self)
        elif self.action == 'blink':
            self.led.blink(self, onDuration, offDuration)

    def untrigger(self, **kargs):
        self.led.turn_off(self)

    def __repr__(self):
        return "SetLed(%s, %s)" % (self.led, self.action)

