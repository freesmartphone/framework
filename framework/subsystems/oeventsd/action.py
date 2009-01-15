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

__version__ = "0.2.0"
MODULE_NAME = "oeventsd.action"

from parser import AutoFunction

from framework.patterns import decorator

import dbus
import Queue

import logging
logger = logging.getLogger( MODULE_NAME )

#============================================================================#
class Action(AutoFunction):
#============================================================================#
    """
    Base class for Action objects

    An action has a `trigger` and `untrigger` methods.
    By default the untrigger method will do nothing, but if it make sense, the action
    should define it.
    """

    #
    # public
    #
    def __init__( self ):
        AutoFunction.__init__( self )

    def trigger( self, **kwargs ):
        pass

    def untrigger( self, **kwargs ):
        pass

    def __repr__( self ):
        return "unamed action"

#============================================================================#
class ListAction(list, Action):
#============================================================================#
    """
    An action that will trigger a sequence of actions

    This is basically a script.
    """
    def __init__( self, actions ):
        list.__init__( self, actions )
        Action.__init__( self )

    def trigger( self, **kwargs ):
        for action in self:
            action.trigger( **kwargs )

    def untrigger( self, **kwargs ):
        for action in self:
            action.untrigger( **kwargs )

#============================================================================#
class DebugAction(Action):
#============================================================================#
    """
    A special action for debugging purposes
    """
    function_name = 'Debug'

    def __init__(self, msg):
        Action.__init__( self )
        self.msg = msg
    def trigger(self, **kargs):
        logger.info("DebugAction : %s", self.msg)
    def __repr__(self):
        return "Debug(\"%s\")" % self.msg

#============================================================================#
class DBusAction(Action):
#============================================================================#
    """
    A special action that will call a DBus method.
    """

    #FIXME: Add Cache for dbus objects

    def __init__(self, bus, service, obj, interface, method, *args):
        Action.__init__( self )
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

    def trigger(self, **kargs):
        # Get the Dbus object
        object = self.bus.get_object(self.service, self.obj)
        iface = dbus.Interface(object, dbus_interface=self.interface)
        logger.info("call dbus method %s %s(%s)", self.obj, self.method, self.args)
        # Get the method
        method = getattr(iface, self.method)
        # We make the call asynchronous, cause we don't want to block the main loop
        kargs = {'reply_handler':self.on_reply, 'error_handler':self.on_error}
        method(*self.args, **kargs)

    def on_reply(self, *args):
        # We don't pass the reply to anything
        logger.info("method %s responded: %s", self.method, args)

    def on_error(self, error):
        logger.error("method %s emited error: %s", self.method, error)

    def __repr__(self):
        return "%s(%s)" % (self.method, self.args)

#============================================================================#
class QueuedDBusAction( DBusAction ):
#============================================================================#
    q = Queue.Queue()

    def enqueue( self, method, args, kargs ):
        logger.debug( "enqueing dbus call %s.%s", method, args )
        relaunch = ( self.q.qsize() == 0 )
        self.q.put( ( method, args, kargs ) )
        if relaunch:
            self.workDaQueue()

    def workDaQueue( self ):
        logger.debug( "working on queue w/ size %d", self.q.qsize() )
        if self.q.qsize():
            method, args, kargs = self.q.get()
            # async dbus call now
            method( *args, **kargs )

    def trigger( self, **kargs ):
        # Get the Dbus object
        object = self.bus.get_object(self.service, self.obj)
        iface = dbus.Interface(object, dbus_interface=self.interface)
        logger.info("call dbus signal %s %s(%s)", self.obj, self.method, self.args)
        # Get the method
        method = getattr(iface, self.method)
        kargs = {'reply_handler':self.on_reply, 'error_handler':self.on_error}
        # Enqueue / Launch
        self.enqueue( method, self.args, kargs )

    def on_reply(self, *args):
        # We don't pass the reply to anything
        logger.info("signal %s responded : %s", self.method, args)
        self.workDaQueue()

    def on_error(self, error):
        logger.error("signal %s emited an error %s", self.method, error)
        self.workDaQueue()
