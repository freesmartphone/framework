#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

#=========================================================================#
def logged( fn ):
#=========================================================================#
    """
    This decorator logs the name of a function or, if applicable,
    a method including the classname.
    """
    import inspect
    def logIt( *args, **kwargs ):
        calldepth = len( inspect.stack() )
        try:
            classname = args[0].__class__.__name__
        except AttributeError:
            classname = ""
        print "%s> %s.%s: ENTER" % ( '|...' * calldepth, classname, fn.__name__ )
        result = fn( *args, **kwargs )
        print "%s> %s.%s: LEAVE" % ( '|...' * calldepth, classname, fn.__name__ )
        return result
    return logIt

