#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

# FUNCTION_DEBUG = False
FUNCTION_DEBUG = True

colorclasses = { "MiscChannel": 38, "CallChannel": 35, "UnsolicitedResponseChannel": 31 }

#=========================================================================#
def logged( fn ):
#=========================================================================#
    """
    Decorator that logs the name of a function each time it is called.
    If the function is a bound method, it also prints the classname.
    """
    if not FUNCTION_DEBUG:
        return fn
    import inspect, random

    def logIt( *args, **kwargs ):
        calldepth = len( inspect.stack() )
        try:
            classname = args[0].__class__.__name__
        except AttributeError:
            classname = ""
        colorpre = ""
        colorpost = ""
        if classname:
            if classname not in colorclasses:
                colorclasses[classname] = random.randrange( 30, 47 )
            colorpre = "\033[1;%dm" % colorclasses[classname]
            colorpost = "\033[m"
        print colorpre,
        print "%s> %s.%s: ENTER %s,%s" % ( '|...' * calldepth, classname, fn.__name__, repr(args[1:]), repr(kwargs) ),
        print colorpost
        result = fn( *args, **kwargs )
        print colorpre,
        print "%s> %s.%s: LEAVE" % ( '|...' * calldepth, classname, fn.__name__ ),
        print colorpost

        return result

    logIt.__dict__ = fn.__dict__
    logIt.__name__ = fn.__name__
    logIt.__doc__ = fn.__doc__
    return logIt

#=========================================================================#
def dbuscalls( fn ):
#=========================================================================#
    """
    Call it like:
    @dbuscalls
    def getInfoFromObject():
        yield object.method()
    """
    def dbusGen( *args, **kwargs ):
        return fn( args, kwargs )

    dbusGen.__dict__ = fn.__dict__
    dbusGen.__name__ = fn.__name__
    dbusGen.__doc__ = fn.__doc__
    return dbusGen
