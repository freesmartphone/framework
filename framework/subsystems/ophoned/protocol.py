# -*- coding: UTF-8 -*-
"""
The Open Phone Daemon - Python Implementation

(C) 2008 Guillaume "Charlie" Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned
"""

import dbus
import dbus.service
from dbus import DBusException

import logging
logger = logging.getLogger('ophoned.protocol')

class ProtocolMetaClass(type):
    """The meta class for Protocole class

        We use this meta class to keep track of all the Protocols instances
    """
    def __init__(cls, name, bases, dict):
        super(ProtocolMetaClass, cls).__init__(name, bases, dict)
        if bases[0] != object:  # We don't want to register the base Protocol class
            Protocol.subclasses[name] = cls

class ProtocolUnusable(Exception):
    """This exception can be raised in the __init__ method of any protocol to indicate that it can't be used"""
    def __init__(self, msg = None):
        super(ProtocolUnusable, self).__init__(msg)

class Protocol(object):
    """Represent a phone call protocol

       To create a new protocol just subclass this class
       One instance of each protocol will be created by the meta class at import time.

       Every Protocol class should define an inner Call class
    """
    __metaclass__ = ProtocolMetaClass
    subclasses = {} # Contain all the subclasses of Protocol

    def name(self):
        raise NotImplemented

    def __init__(self, phone):
        logger.info("creating protocol %s", self.name() )
        self.phone = phone
        self.path = "/org/freesmartphone/Phone/%s" % self.name()
        self.next_call_handle = 0
        self.calls = {} # We keep a map : number -> call for every calls

    def fini( self ):
        logger.info("removing protocol %s", self.name() )

    def CreateCall(self, peer):
        """Return a new chanel targeting the given number

            if force is True and a call on this number is already present, then the call will be removed
        """
        # Every Protocl class need to define an inner Call class
        call = self.__class__.Call(self, self.next_call_handle, peer)
        self.calls[call.handle] = call
        self.next_call_handle += 1
        return call

    def remove(self, call):
        """This mehtod is called when a call need to be removed"""
        del self.calls[call.handle]

class Call(dbus.service.Object):
    """A Call object represents a communication channel"""
    def __init__(self, protocol, handle, peer):
        """Create a new Call
           arguments:
           protocol -- The protocol object we use for this call
           handle   -- A unique handle for the call
        """
        self.path = "%s/%s" % (protocol.path, handle)
        super(Call, self).__init__(protocol.phone.bus, self.path)
        self.protocol = protocol
        self.handle = handle
        self.peer = peer # TODO: change the name to number, because in fact it is exactly that
        self.status = 'Idle'
        self.protocol.phone.CallCreated(self)

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def GetPeer(self):
        """Return the number of the peer (usually the number of the call)"""
        return self.peer

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def Initiate(self):
        """Initiate the call

           The call will be effectively initiated when we receive the 'Activated' Signal
        """
        self.status = 'Initiating'
        return self.status

    @dbus.service.method(
        'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
        async_callbacks=("dbus_ok","dbus_error")
    )
    def Activate(self, dbus_ok, dbus_error):
        """Accept the call"""
        self.status = 'Activating'
        dbus_ok(self.status)

    @dbus.service.method(
        'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
        async_callbacks=("dbus_ok","dbus_error")
    )
    def Release(self, dbus_ok, dbus_error):
        """Release the call"""
        self.status = 'Releasing'
        dbus_ok(self.status)

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def GetStatus(self):
        """Return the current status of the call"""
        return self.status

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='')
    def Remove(self):
        """Remove the call object when it is not needed anymore

           After the call has been removed, its DBus object is released, so we can't receive events from it anymore
        """
        self.remove_from_connection()
        self.protocol.remove(self)

    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Outgoing(self):
        """Emitted when the call status changes to Outgoing"""
        self.status = 'Outgoing'

    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Released(self):
        """Emitted when the call status changes to Released"""
        self.status = 'Released'
        self.protocol.phone.CallReleased(self)

    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Activated(self):
        """Emitted when the call status changes to Active"""
        self.status = 'Active'




