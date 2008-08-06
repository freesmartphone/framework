
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

from filter import Filter
from action import Action

# TODO : add a way to deactivate a rule

class Rule(object):
    """Event Rule object
    
       A Rule consist of :
       - a trigger
       - a list of filters
       - a list of actions
       
       The way it works is the following :
       When the trigger is activated, and if all the filter match the signal emitted by the trigger,
       The all the actions will be called.
       
       The signal is passed in form of keywords arguments in the __call__ method 
    """
    def __init__(self, trigger, filters, actions):
        """Create a new rule
        
           We need to call the init method of the rule before
           it will actually be actvated
        """
        if not isinstance(filters, list):
            filters = [filters]
        if not isinstance(actions, list):
            actions = [actions]
            
        assert all(isinstance(x, Filter) for x in filters)
        assert all(isinstance(x, Action) for x in actions) 
        
        self.trigger = trigger
        trigger.connect(self)
        self.filters = filters
        self.actions = actions
        
        logger.info("Creating new rule : %s", self)
    
    def __repr__(self):
        return "on %s if %s then %s" % (self.trigger, self.filters, self.actions)
        
    def on_signal(self, **kargs):
        # First we check that ALL the filters match the signal
        if any(not filter(**kargs) for filter in self.filters):
            return
        # If it is the case, then we start all the actions
        for c in self.actions:
            c(**kargs)
            
    def init(self):
        """After we call this method, the rule is active"""
        logger.info("init rule : %s", self)
        self.trigger.init()
            

