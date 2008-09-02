# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import logging
logger = logging.getLogger('oeventsd')

import dbus

#============================================================================#
class ActionMetaClass(type):
#============================================================================#
    """The meta class for Action class"""
    def __init__(cls, name, bases, dict):
        # If an action has a class attribute : 'function_name',
        # Then we create a new function of that name that create this action
        super(ActionMetaClass, cls).__init__(name, bases, dict)
        if 'function_name' in dict:
            def func(*args):
                return cls(*args)
            from parser import Function
            Function.register(dict['function_name'], func)

#============================================================================#
class Action(object):
#============================================================================#
    """
    An action is a functor object that is called by a rule
    """
    __metaclass__ = ActionMetaClass

    def __init__(self):
        pass
    def __call__(self, **kargs):
        logger.info("%s called", self)
    def __repr__(self):
        return "unamed action"

#============================================================================#
class DebugAction(Action):
#============================================================================#
    """
    A special action for debugging purposes
    """
    function_name = 'Debug'

    def __init__(self, msg):
        self.msg = msg
    def __call__(self, **kargs):
        logger.info("DebugAction : %s", self.msg)
    def __repr__(self):
        return "Debug(\"%s\")" % self.msg

#============================================================================#
class DBusAction(Action):
#============================================================================#
    """
    A special action that will call a DBus method
    """
    def __init__(self, bus, service, obj, interface, method, *args):
        super(DBusAction, self).__init__()
        self.bus = bus
        # some arguments checking
        assert isinstance(service, str)
        assert isinstance(obj, str)
        assert isinstance(interface, str)
        assert isinstance(method, str)
        self.bus = bus
        self.service = service
        self.obj = obj
        self.interface = interface
        self.method = method
        self.args = args

    def __call__(self, **kargs):
        # Get the Dbus object
        object = self.bus.get_object(self.service, self.obj)
        iface = dbus.Interface(object, dbus_interface=self.interface)
        logger.info("call dbus signal %s %s(%s)", self.obj, self.method, self.args)
        # Get the method
        method = getattr(iface, self.method)
        # We make the call asynchronous, cause we don't want to block the main loop
        kargs = {'reply_handler':self.on_reply, 'error_handler':self.on_error}
        method(*self.args, **kargs)

    def on_reply(self, *args):
        # We don't pass the reply to anything
        logger.info("signal %s responded : %s", self.method, args)

    def on_error(self, error):
        logger.error("signal %s emited an error %s", self.method, error)

    def __repr__(self):
        return "%s(%s)" % (self.method, self.args)

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

