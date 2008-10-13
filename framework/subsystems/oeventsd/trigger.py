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

from parser import AutoFunction

#============================================================================#
class Trigger(AutoFunction):
#============================================================================#
    """A trigger is the initial event that can activate a rule.

       When a trigger is activated, it call the rule `trigger` method,
       giving a set of keywork arguments (the signal attributes to the method)
       Then the rule can decide to start or not its actions.
       
       A trigger can also optionaly have a an `untrigger` method. This method will
       call the `untrigger` method of the connected rules.
    """

    def __init__(self):
        """Create a new trigger

           The trigger need to be initialized with the `init` method before
           it can trigger the connected rules
        """
        self.__listeners = []     # List of rules that are triggered by this trigger

    def connect(self, action):
        """Connect the trigger to an action

           This method should only be called by the Rule class
        """
        self.__listeners.append(action)

    def _trigger(self, **kargs):
        """Trigger all the connected rules"""
        logger.debug("trigger %s", self)
        for action in self.__listeners:
            action.trigger(**kargs)
            
    def _untrigger(self, **kargs):
        """untrigger all the connected rules"""
        logger.debug("untrigger %s", self)
        for action in self.__listeners:
            action.untrigger(**kargs)

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
        self.dbus_match = None

    def enable(self):
        if self.dbus_match is not None: # if the rule is already enabled we do nothing 
            return
        # Connect to the DBus signal
        logger.debug("connect trigger to dbus signal %s %s", self.obj, self.signal)
        self.dbus_match = self.bus.add_signal_receiver(
            self.on_signal,
            dbus_interface=self.interface,
            signal_name=self.signal
        )
        
    def disable(self):
        if self.dbus_match is None: # if the rule is already disabled we do nothing 
            return
        self.dbus_match.remove()
        self.dbus_match = None

    def on_signal(self, *args):
        self._trigger(args=args)

#============================================================================#
class TestTrigger( Trigger ):
#============================================================================#
    """This trigger can be used ot debug the events system.
    
    It is triggered when oeventsd.TriggerTest method is called
    """
    function_name = "Test"
    
    def __init__( self, name ):
        super( TestTrigger, self ).__init__()
        self.name = name
        
    def __repr__( self ):
        return "Test(%s)" % self.name
    
