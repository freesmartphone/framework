# -*- coding: utf-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: fso_triggers
"""

from trigger import DBusTrigger
from rule import WhileRule

import dbus

import logging
logger = logging.getLogger('oeventsd.fso_triggers')

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
        self._trigger(id=id, status=status, properties=properties)

    def __repr__(self):
        return "CallStatus"

# TODO: Maybe this should be an instance of a special class (Condition ?)
#============================================================================#
class CallListContains(WhileRule):
#============================================================================#
    """This rule keep track of all the calls, and can be used to check for a given status in one of them"""
    function_name = "CallListContains"

    def __init__(self, status):
        self.status = status.lower()
        self.calls = {} # The list of current call object
        super(CallListContains, self).__init__(CallStatusTrigger())

    def trigger(self, id=None, status=None, properties=None, **kargs):
        logger.debug("Trigger %s", self)
        self.calls[id] = None
        if status:
            self.calls[id] = status.lower()
        if self.status in self.calls.values():
            super(CallListContains, self).trigger()
        else:
            super(CallListContains, self).untrigger()

    # needed to fix Bug #2305                                                          
    # The filter functions need a patch, because they evaluate 
    # from outside to inside, that would not corerctly evaluate terms like
    # Or(CallListContains("outgoing"), CallListContains("active"))
    # because the CallListContains status gets updates after Or was called
    def filter( self, id=None, status=None, properties=None, **kargs ):
        """The filter is True if the rule is triggered"""                                                
        self.trigger(id, status, properties, **kargs)
        return self.triggered                                                                            

    def __repr__(self):
        return "CallListContains(%s)" % self.status

#============================================================================#
class BTHeadsetConnectedTrigger(DBusTrigger):
#============================================================================#
    function_name = 'BTHeadsetConnected'

    def __init__(self):
        bus = dbus.SystemBus()
        super(BTHeadsetConnectedTrigger, self).__init__(
            bus,
            'org.freesmartphone.ophoned',
            '/org/freesmartphone/Phone',
            'org.freesmartphone.Phone',
            'BTHeadsetConnected'
        )
    def on_signal(self, status):
        logger.info("Receive BTConnectedEnabled, status = %s", status)
        self._trigger(status=status)

    def __repr__(self):
        return "BTHeadsetConnected"

#============================================================================#
class BTHeadsetIsConnected(WhileRule):
#============================================================================#
    function_name = "BTHeadsetIsConnected"

    def __init__(self):
        super(BTHeadsetIsConnected, self).__init__(BTHeadsetConnectedTrigger())

    def trigger(self, status=None, **kargs):
        logger.debug("Trigger %s", self)
        if status:
            super(BTHeadsetIsConnected, self).trigger()
        else:
            super(BTHeadsetIsConnected, self).untrigger()

    def __repr__(self):
        return "BTHeadsetIsConnected()"

#============================================================================#
class NewMissedCallsTrigger(DBusTrigger):
#============================================================================#
    """
    A custom dbus trigger for org.freesmartphone.PIM.Calls.NewMissedCalls
    """

    function_name = 'NewMissedCallsTrigger'

    def __init__(self):
        bus = dbus.SystemBus()
        super(NewMissedCallsTrigger, self).__init__(
            bus,
            'org.freesmartphone.opimd',
            '/org/freesmartphone/PIM/Calls',
            'org.freesmartphone.PIM.Calls',
            'NewMissedCalls'
        )
    def on_signal(self, status):
        logger.info("Receive NewMissedCalls = %s" % status)
        self._trigger(status=status)

    def __repr__(self):
        return "NewMissedCallsTrigger"

#============================================================================#
class NewMissedCalls(WhileRule):
#============================================================================#
    function_name = "NewMissedCalls"

    def __init__(self):
        super(NewMissedCalls, self).__init__(NewMissedCallsTrigger())

    def trigger(self, status=None, **kargs):
        logger.debug("Trigger %s", self)
        logger.info("NewMissedCalls %d", status)
        if status:
            super(NewMissedCalls, self).trigger()
        else:
            super(NewMissedCalls, self).untrigger()

    def __repr__(self):
        return "NewMissedCalls()"

#============================================================================#
class UnreadMessagesTrigger(DBusTrigger):
#============================================================================#
    """
    A custom dbus trigger for org.freesmartphone.PIM.Messages.UnreadMessages
    """

    function_name = 'UnreadMessagesTrigger'

    def __init__(self):
        bus = dbus.SystemBus()
        super(UnreadMessagesTrigger, self).__init__(
            bus,
            'org.freesmartphone.opimd',
            '/org/freesmartphone/PIM/Messages',
            'org.freesmartphone.PIM.Messages',
            'UnreadMessages'
        )
    def on_signal(self, status):
        logger.info("Receive UnreadMessages = %s" % status)
        self._trigger(status=status)

    def __repr__(self):
        return "UnreadMessagesTrigger"

#============================================================================#
class UnreadMessages(WhileRule):
#============================================================================#
    function_name = "UnreadMessages"

    def __init__(self):
        super(UnreadMessages, self).__init__(UnreadMessagesTrigger())

    def trigger(self, status=None, **kargs):
        logger.debug("Trigger %s", self)
        logger.info("UnreadMessages %d", status)
        if status:
            super(UnreadMessages, self).trigger()
        else:
            super(UnreadMessages, self).untrigger()

    def __repr__(self):
        return "UnreadMessages()"

#============================================================================#
class IncomingMessageTrigger(DBusTrigger):
#============================================================================#
    """
    A custom dbus trigger for org.freesmartphone.GSM.SMS.IncomingTextMessage
    """

    function_name = 'IncomingMessage'

    def __init__(self):
        bus = dbus.SystemBus()
        super(IncomingMessageTrigger, self).__init__(
            bus,
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/SMS',
            'org.freesmartphone.GSM.SMS',
            'IncomingTextMessage'
        )
    def on_signal(self, number, timestamp, contents):
        logger.info("Received IncomingMessage from = %s" % number)
        self._trigger(number=number)

    def __repr__(self):
        return "IncomingMessage"

#============================================================================#
class IncomingUssdTrigger(DBusTrigger):
#============================================================================#
    """
    A custom dbus trigger for org.freesmartphone.GSM.Network.IncomingUssd
    """

    function_name = 'IncomingUssd'

    def __init__(self):
        bus = dbus.SystemBus()
        super(IncomingUssdTrigger, self).__init__(
            bus,
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/Device',
            'org.freesmartphone.GSM.Network',
            'IncomingUssd'
        )
    def on_signal(self, status, content):
        logger.info("Receive IncomingUssd with status = %s" % status)
        self._trigger(status=status, content=content)

    def __repr__(self):
        return "IncomingUssd"

#============================================================================#
class PowerStatusTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Device.PowerSupply.PowerStatus
    """

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
        self._trigger(status=status)

    def __repr__(self):
        return "PowerStatus"

#============================================================================#
class IdleStateTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Device.IdleNotifier.State
    """

    function_name = 'IdleState'

    def __init__(self):
        bus = dbus.SystemBus()
        super(IdleStateTrigger, self).__init__(
            bus,
            'org.freesmartphone.odeviced',
            None,
            'org.freesmartphone.Device.IdleNotifier',
            'State'
        )
    def on_signal(self, status):
        logger.info("Receive IdleState, status = %s", status)
        self._trigger(status=status)

    def __repr__(self):
        return "IdleState"

#============================================================================#
class TimeTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Time.Minute
    """

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
            self._trigger()

    def __repr__(self):
        return "Time(%d:%d)" % (self.hour, self.minute)

#============================================================================#
class InputTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Input.Event
    """

    function_name = 'InputEvent'

    def __init__(self):
        bus = dbus.SystemBus()
        super(InputTrigger, self).__init__(
            bus,
            'org.freesmartphone.odeviced',
            '/org/freesmartphone/Device/Input',
            'org.freesmartphone.Device.Input',
            'Event'
        )
    def on_signal(self, switch, event, duration):
        logger.debug("%s triggered", self)
        self._trigger(switch=switch, event=event, duration=duration)

    def __repr__(self):
        return "InputTrigger"

#============================================================================#
class KeypadTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.GSM.Device.KeypadEvent
    """

    function_name = 'KeypadEvent'

    def __init__(self):
        bus = dbus.SystemBus()
        super(KeypadTrigger, self).__init__(
            bus,
            'org.freesmartphone.ogsmd',
            '/org/freesmartphone/GSM/Device',
            'org.freesmartphone.GSM.Device',
            'KeypadEvent'
        )
    def on_signal(self, name, pressed):
        logger.debug("%s triggered", self)
        self._trigger(name=name, pressed=pressed)

    def __repr__(self):
        return "KeypadTrigger"

#============================================================================#
class BacklightPowerTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Device.Display.BacklightPower
    """

    function_name = 'BacklightPower'

    def __init__(self):
        bus = dbus.SystemBus()
        super(BacklightPowerTrigger, self).__init__(
            bus,
            'org.freesmartphone.odeviced',
            None,
            'org.freesmartphone.Device.Display',
            'BacklightPower'
        )

    def on_signal(self, status):
        logger.info("Receive BacklightPower, status = %s", status)
        self._trigger(status=status)

    def __repr__(self):
        return "BacklightPower"

#============================================================================#
class ResourceStateTrigger(DBusTrigger):
#============================================================================#
    """
    A dbus trigger for org.freesmartphone.Usage.ResourceChanged
    """
    function_name = 'ResourceState'

    def __init__(self):
        bus = dbus.SystemBus()
        super(ResourceStateTrigger, self).__init__(
            bus,
            'org.freesmartphone.ousaged',
            '/org/freesmartphone/Usage',
            'org.freesmartphone.Usage',
            'ResourceChanged'
        )
    def on_signal(self,resource,state,attributes):
        power_status = "enabled" if state  else "disabled"
        logger.info("%s is now %s", resource, power_status)
        self._trigger(resource=resource,power_state=power_status)
    def __repr__(self):
        return "ResourceState"

