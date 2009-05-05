# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: oevents
"""

__version__ = "0.3.1"

import gobject
import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'oevents' )

from framework.controller import Controller

from action import Action
from parser import Parser
from trigger import TestTrigger

# FIXME: treat custom triggers, actions, and filters as plugins and load them on demand
from fso_actions import *
from fso_triggers import *
from leds_actions import *

# TODO:
# - Add a way to dynamically remove events
# - Add a way to add new events when the event conf file is modified

#============================================================================#
class EventsManager(dbus.service.Object):
#============================================================================#
    """This is the interface to the event service

       In prcatice we shouldn't have to use this too much,
       because the events can be defined into a configuration file.
    """
    def __init__(self, bus):
        # Those attributes are needed by the framework system
        self.path = '/org/freesmartphone/Events'
        self.interface = 'org.freesmartphone.Events'
        self.bus = bus

        super(EventsManager, self).__init__(bus, self.path)
        # The set of rules is empty
        self.rules = []
        logger.info( "%s %s initialized. Serving %s at %s", self.__class__.__name__, __version__, self.interface, self.path )

        # We need to update the rule every time the 'preferences/rules/enabled-rules' list is modified
        bus = dbus.SystemBus()
        bus.add_signal_receiver(
            self.on_rules_enabled_modified, 'Notify', 'org.freesmartphone.Preferences.Service',
            'org.freesmartphone.opreferencesd', '/org/freesmartphone/Preferences/rules'
        )

    def add_rule(self, rule):
        """Add a new rule into the event manager"""
        self.rules.append(rule)

    def on_rules_enabled_modified(self, *args):
        self.update()

    def update(self):
        """Enable the rules that need to be"""
        logger.info("Updating the rules")
        # First we need to get the 'enabled-rules' value from the 'rules' preference service
        try:
            prefs = Controller.object( "/org/freesmartphone/Preferences" )
        except KeyError: # preferences service not online
            logger.warning( "Can't access /org/freesmartphone/Preferences. Rules will be limited." )
            # FIXME can we do something (limited) without preferences or not?
            return False

        rules_prefs = prefs.GetService( "rules" )
        enabled_rules = rules_prefs.GetValue( "enabled-rules" )
        enabled_rules = [str(x) for x in enabled_rules]

        for rule in self.rules:
            if rule.name in enabled_rules:
                rule.enable()
            else:
                rule.disable()

        return False

    @dbus.service.method( "org.freesmartphone.Events" , in_signature='sb' )
    def TriggerTest( self, name, value = True ):
        """Trigger or untrigger all the 'Test' triggers with matching names

        This method is only here for testing purpose.
        :arguments:
        name : the name of the Test triggers to trigger/untrigger
        value : True to trigger, False to untrigger
        """
        for rule in self.rules:
            trigger = rule._Rule__trigger
            if isinstance( trigger, TestTrigger ) and trigger.name == name:
                if value:
                    trigger._trigger()
                else:
                    trigger._untrigger()

    @dbus.service.method( "org.freesmartphone.Events" , in_signature='s' )
    def AddRule( self, rule_str ):
        """Parse a rule string and add it into the rule list"""
        rule_str = str( rule_str )
        parser = Parser()
        rule = parser.parse_rule( rule_str )
        logger.info( "Add rule %s", rule )
        self.add_rule(rule)
        self.update()

    @dbus.service.method( "org.freesmartphone.Events" , in_signature='s' )
    def RemoveRule( self, name ):
        """Remove a rule by name"""
        for rule in self.rules[:]:
            if rule.name == name:
                logger.info( "Removing rule %s", name )
                self.rules.remove(rule)

    @dbus.service.method( "org.freesmartphone.Events" )
    def ReloadRules( self ):
        """Reload all rules"""
        self.update()

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    events_manager = EventsManager(controller.bus)

    # Get the initial rules files
    parser = Parser()
    rules_file = os.path.join( rootdir, 'rules.yaml' )
    rules = parser.parse_rules(open(rules_file).read())
    for rule in rules:
        events_manager.add_rule(rule)

    # This is to ensure that all the other subsystems are up before we update the events_manager
    gobject.idle_add( events_manager.update )

    # Return the dbus object to the framework
    return [events_manager]
