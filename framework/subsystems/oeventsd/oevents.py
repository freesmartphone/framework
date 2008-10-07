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

__version__ = "0.3.0"

from framework.config import config
from framework.controller import Controller

from action import Action
from parser import Parser

# FIXME: treat custom triggers, actions, and filters as plugins and load them on demand
from fso_actions import *
from fso_triggers import *

import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

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
        logger.info("update the rules")
        # First we need to get the 'enabled-rules' value from the 'rules' preference service
        prefs = Controller.object( "/org/freesmartphone/Preferences" )
        rules_prefs = prefs.GetService( "rules" )
        enabled_rules = rules_prefs.GetValue( "enabled-rules" )
        enabled_rules = [str(x) for x in enabled_rules]
        
        for rule in self.rules:
            if rule.name in enabled_rules:
                rule.enable()
            else:
                rule.disable()

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called by the framework module manager"""
    events_manager = EventsManager(controller.bus)

    # Get the initial rules files
    # We can set a list of possible path in the config file
    possible_rule_files = config.getValue("oeventsd", "rules_file", "").split(':')
    logger.debug("rules files are : %s", possible_rule_files)
    parser = Parser()
    # Now we try to parse the rules from the first existing rule file
    for path in possible_rule_files:
        if os.path.exists(path):
            logger.info("parsing rules from file %s", path)
            rules = parser.parse_rules(open(path).read())
            for rule in rules:
                events_manager.add_rule(rule)
            break   # We only use the first file
    events_manager.update()

    # Return the dbus object to the framework
    return [events_manager]
