# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

class Filter(object):
    def __call__(self, **kargs):
        raise NotImplementedError

    def __invert__(self):   # The ~ operator
        return InvertFilter(self)

class AttributeFilter(Filter):
    def __init__(self, **kargs):
        self.kargs = kargs
    def __call__(self, **kargs):
        return all( key in kargs and kargs[key] == value for (key, value) in self.kargs.items() )

    def __repr__(self):
        return "and".join( "%s == %s" % (key, value) for (key, value) in self.kargs.items() )

class InvertFilter(Filter):
    def __init__(self, filter):
        super(InvertFilter, self).__init__()
        self.filter = filter
    def __call__(self, **kargs):
        return not self.filter(**kargs)

    def __repr__(self):
        return "~(%s)" % self.filter


