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

import logging
logger = logging.getLogger('oeventsd')
import dbus

import framework.patterns.tasklet as tasklet

from action import Action, DBusAction

class Led(object):
    """Led object
    
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
        bus = dbus.SystemBus()
        service = 'org.freesmartphone.odeviced'
        obj = '/org/freesmartphone/Device/LED/%s' % device
        interface = 'org.freesmartphone.Device.LED'
        dbus_obj = bus.get_object(service, obj, follow_name_owner_changes=True)
        self.interface = dbus.Interface(dbus_obj, interface)
        
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
        self.interface.SetBlinking(100, 1500, reply_handler=self.on_reply, error_handler=self.on_error)
        
    def turn_on(self, user):
        self.users[user] = 'on'
        self.__update()
    def turn_off(self, user):
        if user in self.users:
            del self.users[user]
        else:
            logger.warning("try to turn off led %s before having turing it on", self)
        self.__update()
    def blink(self, user):
        self.users[user] = 'blink'
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

    def __init__(self, device, action):
        Action.__init__( self )
        self.led = Led(device)
        self.action = action
        if not action in ['light', 'blink']:
            logger.error("Unhandeled action on led %s : %s", device, action)
    def trigger(self, **kargs):
        if self.action == 'light':
            self.led.turn_on(self)
        elif self.action == 'blink':
            self.led.blink(self)
    def untrigger(self, **kargs):
        self.led.turn_off(self)
    def __repr__(self):
        return "SetLed(%s, %s)" % (self.led, self.action)
