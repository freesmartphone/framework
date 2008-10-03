# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: action
"""

import dbus

import logging
logger = logging.getLogger('oeventsd')

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
    """Base class for Action objects
    
    An action has a `do` and `undo` methods.
    By default the undo method will do nothing, but if it make sense, the action
    should define it.
    """
    __metaclass__ = ActionMetaClass

    def __init__(self):
        pass
    def do(self, **kargs):
        pass
    def undo(self, **kargs):
        pass
    def __repr__(self):
        return "unamed action"

#============================================================================#
class DebugAction(Action):
#============================================================================#
    """A special action for debugging purposes
    """
    function_name = 'Debug'

    def __init__(self, msg):
        self.msg = msg
    def do(self, **kargs):
        logger.info("DebugAction : %s", self.msg)
    def __repr__(self):
        return "Debug(\"%s\")" % self.msg

#============================================================================#
class DBusAction(Action):
#============================================================================#
    """A special action that will call a DBus method.
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

    def do(self, **kargs):
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
