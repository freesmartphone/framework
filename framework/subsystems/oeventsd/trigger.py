# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import logging
logger = logging.getLogger('oeventsd')

import dbus

class Trigger(object):
    """A trigger is the initial event that will activate a rule.

       When a trigger is activated, it call the rule __call__ method,
       giving a set of keywork arguments (the signal attributes to the method)
       Then the rule can decide to start or not its actions.
    """
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

class DBusTrigger(Trigger):
    """A special trigger that wait for a given DBus signal to trigger its rules"""
    def __init__(self, bus, service, obj, interface, signal):
        super(DBusTrigger, self).__init__()
        # some arguments checking
        assert isinstance(service, str)
        assert isinstance(obj, str)
        assert isinstance(interface, str)
        assert isinstance(signal, str)
        self.bus = bus
        self.service = service
        self.obj = obj
        self.interface = interface
        self.signal = signal

    def init(self):
        # Connect to the DBus signal
        object = self.bus.get_object(self.service, self.obj)
        iface = dbus.Interface(object, dbus_interface=self.interface)
        logger.info("connect trigger to dbus signal %s %s", self.obj, self.signal)
        iface.connect_to_signal(self.signal, self.on_signal)

    def on_signal(self, *args):
        self(args=args)

class CallStatusTrigger(DBusTrigger):
    """Just a sugar trigger for a GSM call status change"""
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

