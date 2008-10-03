# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: trigger
"""

import logging
logger = logging.getLogger('oeventsd')

import dbus

#============================================================================#
class TriggerMetaClass(type):
#============================================================================#
    """The meta class for Trigger class"""
    def __init__(cls, name, bases, dict):
        super(TriggerMetaClass, cls).__init__(name, bases, dict)
        # If a trigger has a class attribute : 'function_name',
        # Then we create a new function of that name that create this trigger
        if 'function_name' in dict:
            def func(*args):
                return cls(*args)
            from parser import Function
            Function.register(dict['function_name'], func)

#============================================================================#
class Trigger(object):
#============================================================================#
    """A trigger is the initial event that can activate a rule.

       When a trigger is activated, it call the rule `trigger` method,
       giving a set of keywork arguments (the signal attributes to the method)
       Then the rule can decide to start or not its actions.
       
       A trigger can also optionaly have a an `untrigger` method. This method will
       call the `untrigger` method of the connected rules.
    """
    __metaclass__ = TriggerMetaClass

    def __init__(self):
        """Create a new trigger

           The trigger need to be initialized with the `init` method before
           it can trigger the connected rules
        """
        self.listeners = []     # List of rules that are triggered by this trigger

    def connect(self, rule):
        """Connect the trigger to a rule

           This method should only be called by the Rule class
        """
        self.listeners.append(rule)

    def trigger(self, **kargs):
        """Trigger all the connected rules"""
        for rule in self.listeners:
            rule.trigger(**kargs)
            
    def untrigger(self, **kargs):
        """untrigger all the connected rules"""
        for rule in self.listeners:
            rule.untrigger(**kargs)

    def enable(self):
        """Enable the trigger

           The trigger won't trigger the connect rules before this
           method has been called
        """
        pass
        
    def disable(self):
        """Disable the trigger"""
        pass


#============================================================================#
class DBusTrigger(Trigger):
#============================================================================#
    """A special trigger that waits for a given DBus signal to trigger its rules"""
    def __init__(self, bus, service, obj, interface, signal):
        """Create the DBus trigger

        arguments:
        - bus       the DBus bus name
        - service   the DBus name of the service
        - obj       the DBus path of the object
        - interface the Dbus interface of the signal
        - signal    the DBus name of the signal

        """
        super(DBusTrigger, self).__init__()
        # some arguments checking
        assert isinstance(service, str)
        assert obj is None or isinstance(obj, str)
        assert isinstance(interface, str)
        assert isinstance(signal, str)
        self.bus = bus
        self.service = service
        self.obj = obj
        self.interface = interface
        self.signal = signal

    def enable(self):
        # Connect to the DBus signal
        logger.info("connect trigger to dbus signal %s %s", self.obj, self.signal)
        self.dbus_match = self.bus.add_signal_receiver(
            self.on_signal,
            dbus_interface=self.interface,
            signal_name=self.signal
        )
        
    def disable(self):
        self.dbus_match.remove()

    def on_signal(self, *args):
        self.trigger(args=args)

