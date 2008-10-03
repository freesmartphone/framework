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

from filter import Filter
from action import Action

# TODO : I think we could redesign the Rule class by making it both an Action and a Trigger :
#        It is an action connected to its trigger and a trigger connected to it's action
#        This way we could handle the do and undo easily. Right now it is not clear when we actually
#        start the actions.

#============================================================================#
class Rule(object):
#============================================================================#
    """Event Rule object

       A Rule consist of :
       - a trigger
       - a list of filters
       - a list of actions

       The way it works is the following :
       When the trigger is activated, and if all the filter match the signal emitted by the trigger,
       The all the actions `do` method will be called.

       The signal is passed in form of keywords arguments in the trigger and untrigger methods.
       
       An rule can also optionaly be untriggered. If a rule can be untriggered,
       then it will keep state of its current status (triggered or not) and will
       call the actions `undo` method if its condition is not meet or if its trigger
       call the `untrigger` method. 
    """
    def __init__(self, trigger, filters, actions, can_untrigger = False):
        """Create a new rule

           We need to add the rule into the EventManager (with the `add_rule`
           method) before it will actually be activated. 
        """
        # We accept list OR single value as argument
        if not isinstance(filters, list):
            filters = [filters]
        if not isinstance(actions, list):
            actions = [actions]

        assert all(isinstance(x, Filter) for x in filters), "Bad filter argument"
        assert all(isinstance(x, Action) for x in actions), "Bad action parameter"

        self.__trigger = trigger
        # The trigger will call this rule when triggered
        trigger.connect(self)
        self.__filters = filters
        self.__actions = actions
        self.__can_untrigger = can_untrigger
        self.__triggered = False

        logger.info("Creating new rule : %s", self)
        
    # If the rule can't be untriggered, then the `triggered` virtual attribute
    # is always set to False
    def __get_triggered(self):
        return self.__triggered
    def __set_triggered(self, value):
        self.__triggered = value and self.__can_untrigger
    triggered = property(__get_triggered, __set_triggered)

    def __repr__(self):
        type = 'while' if self.__can_untrigger else 'on'
        return "%s %s if %s then %s" % (type, self.__trigger, self.__filters, self.__actions)

    def trigger(self, **kargs):
        """This method is called by a trigger when it is activated
        
        Return True if the actions where actually called.
        """
        # First we check that ALL the filters match the signal
        if any(not filter.filter(**kargs) for filter in self.__filters):
            # If not then we untrigger the rule
            # The `untrigger` method won't do anything it the rule is not already tirggered.
            return self.untrigger(**kargs)
        if self.triggered:
            return
        # If it is the case, then we start all the actions
        logger.info("do the actions of rule %s", self)
        for c in self.__actions:
            c.do(**kargs)
        self.triggered = True
            
    def untrigger(self, **kargs):
        """Untrigger the rule"""
        if not self.triggered:
            return
        logger.info("undo the actions of rule %s", self)
        for c in self.__actions:
            c.undo(**kargs)
        self.triggered = False

    def enable(self):
        """Enable the rule
        
           Right now this method is only called by the EventManager when we add
           a new rule.
        """
        logger.info("enable rule : %s", self)
        self.__trigger.enable()
        
    def disable(self):
        """Disable the rule"""
        logger.info("disable rule : %s", self)
        self.__trigger.disable()
        



