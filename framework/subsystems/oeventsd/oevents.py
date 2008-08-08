# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

from framework.config import config

from trigger import Trigger, CallStatusTrigger
from filter import Filter, AttributeFilter
from action import Action, AudioAction
from parser import Parser
from rule import Rule

import dbus
import os

import logging
logger = logging.getLogger('oeventsd')

# TODO:
# - Add a way to dynamically remove events
# - Add a way to add new events when the event conf file is modified

class EventsManager(dbus.service.Object):
    """This is the interface to the event service

       In prcatice we shouldn't have to use this too much,
       because the events can be defined into a configuration file.
    """
    def __init__(self, bus):
        self.path = '/org/freesmartphone/Events'
        self.interface = 'org.freesmartphone.Events'
        self.bus = bus
        super(EventsManager, self).__init__(bus, self.path)
        self.rules = []

    def add_rule(self, rule):
        self.rules.append(rule)

    @dbus.service.method("org.freesmartphone.Events", in_signature='', out_signature='')
    def Init(self):
        """This method need to be called before the rules are actually effectives"""
        logger.info("init all the rules")
        for rule in self.rules:
            rule.init()



def factory(prefix, controller):
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

    # Return the dbus object to the framework
    return [events_manager]
