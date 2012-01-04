# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: filter

"""

__version__ = "0.2.0"
MODULE_NAME = "oeventsd.filter"

import logging
logger = logging.getLogger( MODULE_NAME )

#============================================================================#
class Filter( object ):
#============================================================================#
    """Base class for every filter

       A filter is used after a rule has been triggered to decide if the actions
       will be called or not. When a rule is triggered, the trigger generate a dict
       of values, that can be later used by the filter.

       All the filters need to implement the filter method, taking an arbitrary
       number of keywords argument (**kargs) representing the event generated dict
       of values. The method returns True if the filter accept the event, False otherwise.
    """
    def __init__( self, *args, **kwargs ):
        pass

    def filter( self, **kargs ):
        # The default filter is always True
        # Fixme: unnecessary and time consuming call due to outside to inside evaluations
        return True

    def __invert__( self ):
        """Return the inverted filter of this filter

           The __invert__ method is called by the `~` operator.
        """
        return InvertFilter( self )

    def __or__( self, f ):
        """Return a filter that is the logical OR operation between this filter and an other filter
        """
        return OrFilter( self, f )

    def __and__( self, f ):
        return AndFilter( self, f )

    def enable( self ):
        """enable the filter

        This is used because some filter need to connect to external signals,
        e.g : WhileRule
        """
        pass

    def disable( self ):
        """disable the filter"""
        pass

    def __repr__( self ):
        return "base filter"

#============================================================================#
class AttributeFilter( Filter ):
#============================================================================#
    """This filter is True if all the keywords argument are present in the
       call and have the given value
    """
    def __init__( self, **kargs ):
        Filter.__init__( self )
        self.kargs = kargs

    def filter( self, **kargs ):
        return all( key in kargs and kargs[key] == value for (key, value) in self.kargs.items() )

    def __repr__( self ):
        return "and".join( "%s == %s" % (key, value) for (key, value) in self.kargs.items() )

#============================================================================#
class InvertFilter( Filter ):
#============================================================================#
    """This filer returns the negation of the argument filter"""
    def __init__( self, filter ):
        Filter.__init__( self )
        self.__filter = filter

    def filter( self, **kargs ):
        return not self.__filter.filter( **kargs )

    def enable( self ):
        self.__filter.enable()

    def disable( self ):
        self.__filter.disable()

    def __repr__( self ):
        return "~(%s)" % self.__filter

#============================================================================#
class AndFilter( Filter ):
#============================================================================#
    """This filter returns the AND logical operation between a list of filters"""
    def __init__( self, *filters ):
        Filter.__init__( self )
        assert all( isinstance( f, Filter ) for f in filters )
        self.filters = filters

    def filter( self, **kargs ):
        return all( f.filter( **kargs ) for f in self.filters )

    def enable( self ):
        for f in self.filters:
            f.enable()

    def disable( self ):
        for f in self.filters:
            f.disable()

    def __repr__( self ):
        return "And(%s)" % ','.join( str( f ) for f in self.filters )

#============================================================================#
class OrFilter( Filter ):
#============================================================================#
    """This filter returns the OR logical operation between a list of filters"""
    def __init__( self, *filters ):
        Filter.__init__( self )
        assert all( isinstance( f, Filter ) for f in filters )
        self.filters = filters

    def filter( self, **kargs ):
        return any( f.filter( **kargs ) for f in self.filters )

    def enable( self ):
        for f in self.filters:
            f.enable()

    def disable( self ):
        for f in self.filters:
            f.disable()

    def __repr__( self ):
        return "Or(%s)" % ','.join( str( f ) for f in self.filters )

