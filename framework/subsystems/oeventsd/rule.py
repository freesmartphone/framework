# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

__version__ = "0.2.0"
MODULE_NAME = "oeventsd.rule"

import logging
logger = logging.getLogger( MODULE_NAME )

from filter import Filter, AndFilter
from action import Action, ListAction
from trigger import Trigger

#============================================================================#
class Rule( Trigger, Action ):
#============================================================================#
    """A Rule is a link betwen a trigger and an action, that can check for conditions

    Using rule we can refine the behavior of a trigger by giving a filter.
    When the rule is triggered it will trigger the action only if its filter
    allow it.
    """
    def __init__( self, trigger, filter = Filter(), action = Action(), name = "" ):
        """Create a new rule given a trigger, a filter and an action

        We can give a list of action or a list of filter instead of a single
        action or filter, in that case the actions will be turned into a ListAction
        and the filters into an AndFilter.
        """
        Trigger.__init__( self )
        Action.__init__( self )

        # We accept list OR single value as argument
        if isinstance( filter, list ):
            filter = AndFilter( *filter )
        if isinstance( action, list ):
            action = ListAction( action )

        assert isinstance(trigger, Trigger)
        assert isinstance(action, Action)
        assert isinstance(filter, Filter)

        self.__trigger = trigger
        # The trigger will call this rule when triggered
        trigger.connect( self )

        self.__filter = filter
        self.__action = action
        self.connect( action )

        self.name = name

    def __repr__( self ):
        if self.name:
            return "'%s'" % self.name
        return "on %s if %s then %s" % ( self.__trigger, self.__filter, self.__action )

    def trigger( self, **kargs ):
        # First we check that ALL the filters match the signal
        if not self.__filter.filter( **kargs ):
            return False
        self._trigger( **kargs )
        return True

    def enable( self ):
        # It should be enough to enable the trigger and the filter
        logger.info( "enable rule : %s", self )
        self.__trigger.enable()
        self.__filter.enable()

    def disable( self ):
        # It should be enough to disable the trigger and the filter
        logger.info( "disable rule : %s", self )
        self.__trigger.disable()
        self.__filter.disable()

#============================================================================#
class WhileRule( Rule, Filter ):
#============================================================================#
    """Special Rule that will also untrigger its action

    We can also use a WhileRule as a filter, the condition is then true if the
    rule is currently triggered.
    """
    def __init__( self, *args ):
        Rule.__init__( self, *args )
        Filter.__init__( self, *args )
        self.triggered = False

    def trigger( self, **kargs ):
        if self.triggered:
            if not self._Rule__filter.filter( **kargs ):
                self.untrigger( **kargs )
        else:
            self.triggered = Rule.trigger( self, **kargs )

    def untrigger( self, **kargs ):
        if not self.triggered:
            logger.warning( "Untrigger for '%s' called, but not yet triggered. Not untriggering" )
            return
        self._untrigger( **kargs )
        self.triggered = False

    def filter( self, **kargs ):
        """The filter is True if the rule is triggered"""
        return self.triggered

    def __repr__( self ):
        if self.name:
            return "'%s'" % self.name
        return "While %s if %s then %s" % ( self._Rule__trigger, self._Rule__filter, self._Rule__action )

