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

import logging
logger = logging.getLogger( "oeventsd" )

#============================================================================#
class Filter(object):
#============================================================================#
    """Base class for every filter

       A filter is used after a rule has been triggered to decide if the actions
       will be called or not. When a rule is triggered, the trigger generate a dict
       of values, that can be later used by the filter.

       All the filters need to implement the __call__ method, taking an arbitrary 
       number of keywords argument (**kargs) representing the event generated dict
       of values. The method returns True if the filter accept the event, False otherwise.
    """
    def __call__(self, **kargs):
        raise NotImplementedError

    def __invert__(self):
        """Return the inverted filter of this filter

           The __invert__ method is called by the `~` operator.
        """
        return InvertFilter(self)

#============================================================================#
class AttributeFilter(Filter):
#============================================================================#
    """This filter is True if all the keywords argument are present in the
       call and have the given value
    """
    def __init__(self, **kargs):
        self.kargs = kargs
    def __call__(self, **kargs):
        return all( key in kargs and kargs[key] == value for (key, value) in self.kargs.items() )

    def __repr__(self):
        return "and".join( "%s == %s" % (key, value) for (key, value) in self.kargs.items() )

#============================================================================#
class InvertFilter(Filter):
#============================================================================#
    """This filer returns the negation of the argument filter"""
    def __init__(self, filter):
        super(InvertFilter, self).__init__()
        self.filter = filter
    def __call__(self, **kargs):
        return not self.filter(**kargs)

    def __repr__(self):
        return "~(%s)" % self.filter

