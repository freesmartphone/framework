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
    """A trigger is the initial event that will activate a rule.

       When a trigger is activated, it call the rule __call__ method,
       giving a set of keywork arguments (the signal attributes to the method)
       Then the rule can decide to start or not its actions.
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

    def __call__(self, **kargs):
        """Trigger all the connected rules"""
        for rule in self.listeners:
            rule.on_signal(**kargs)

    def init(self):
        """initialize the trigger

           The trigger won't trigger the connect rules before this
           method has been called
        """
        pass

#============================================================================#
class DBusTrigger(Trigger):
#============================================================================#
    """A special trigger that wait for a given DBus signal to trigger its rules"""
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

    def init(self):
        # Connect to the DBus signal
        logger.info("connect trigger to dbus signal %s %s", self.obj, self.signal)
        self.bus.add_signal_receiver(
            self.on_signal,
            dbus_interface=self.interface,
            signal_name=self.signal
        )

    def on_signal(self, *args):
        self(args=args)

#============================================================================#
class CallStatusTrigger(DBusTrigger):
#============================================================================#
    """Just a sugar trigger for a GSM call status change"""
    
    function_name = 'CallStatus'
    
    def __init__(self):
        bus = dbus.SystemBus()
        super(CallStatusTrigger, self).__init__(
            bus,
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/Device',
            'org.freesmartphone.GSM.Call',
            'CallStatus'
        )
    def on_signal(self, id, status, properties):
        logger.info("Receive CallStatus, status = %s", status)
        self(id=id, status=status, properties=properties)

    def __repr__(self):
        return "CallStatus"

#============================================================================#
class PowerStatusTrigger(DBusTrigger):
#============================================================================#
    """Just a sugar trigger for a Power management status change"""
    
    function_name = 'PowerStatus'
    
    def __init__(self):
        bus = dbus.SystemBus()
        super(PowerStatusTrigger, self).__init__(
            bus,
            'org.freesmartphone.odeviced',
            None,
            'org.freesmartphone.Device.PowerSupply',
            'PowerStatus'
        )
    def on_signal(self, status):
        logger.info("Receive PowerStatus, status = %s", status)
        self(status=status)

    def __repr__(self):
        return "PowerStatus"

#============================================================================#
class TimeTrigger(DBusTrigger):
#============================================================================#
    function_name = 'Time'

    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        bus = dbus.SystemBus()
        super(TimeTrigger, self).__init__(
            bus,
            'org.freesmartphone.otimed',
            '/org/freesmartphone/Time',
            'org.freesmartphone.Time',
            'Minute'
        )
    def on_signal(self, year, mon, day, hour, min, sec, wday, yday, isdst):
        if self.hour == hour and self.minute == min:
            logger.debug("%s triggered", self)
            self()

    def __repr__(self):
        return "Time(%d:%d)" % (self.hour, self.minute)

