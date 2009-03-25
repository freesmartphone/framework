# -*- coding: UTF-8 -*-
"""
freesmartphone.org Framework Daemon

(C) 2009 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2009 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: helpers
"""

MODULE_NAME = "frameworkd.helpers"

from framework.patterns import decorator

import dbus, types

import logging
logger = logging.getLogger( MODULE_NAME )

def drop_dbus_result( *args ):
    if args:
        logger.warning( "unhandled dbus result: %s", args )

def log_dbus_error( desc ):
    def dbus_error( e, desc = desc ):
        if hasattr(e, "get_dbus_name") and hasattr(e, "get_dbus_message"):
            logger.error( "%s (%s %s: %s)" % ( desc, e.__class__.__name__, e.get_dbus_name(), e.get_dbus_message() ) )
        else:
            logger.error( "%s (%s)" % ( desc, e.__class__.__name__ ) )
    return dbus_error

def dbus_to_python( v ):
    class ObjectPath( object ):
        def __init__( self, path ):
            self.path = str( path )

        def __repr__( self ):
            return "op%s" % repr(self.path)

    if isinstance(v, dbus.Byte) \
        or isinstance(v, dbus.Int64) \
        or isinstance(v, dbus.UInt64) \
        or isinstance(v, dbus.Int32) \
        or isinstance(v, dbus.UInt32) \
        or isinstance(v, dbus.Int16) \
        or isinstance(v, dbus.UInt16) \
        or type(v) == types.IntType:
        return int(v)
    elif isinstance(v, dbus.Double) or type(v) == types.FloatType:
        return float(v)
    elif isinstance(v, dbus.String) or type(v) == types.StringType:
        return str(v)
    elif isinstance(v, dbus.Dictionary) or type(v) == types.DictType:
        return dict( (dbus_to_python(k), dbus_to_python(v)) for k,v in v.iteritems() )
    elif isinstance(v, dbus.Array) or type(v) == types.ListType:
        return [dbus_to_python(x) for x in v]
    elif isinstance(v, dbus.Struct) or type(v) == types.TupleType:
        return tuple(dbus_to_python(x) for x in v)
    elif isinstance(v, dbus.Boolean) or type(v) == types.BooleanType:
        return bool(v)
    elif isinstance(v, dbus.ObjectPath) or type(v) == ObjectPath:
        return ObjectPath(v)
    else:
        raise TypeError("can't convert type %s to python object" % type(v))

@decorator.decorator
def exceptionlogger( f, *args, **kw ):
    """
    This decorator is used to log exceptions thrown in event handlers
    """
    try:
        return f( *args, **kw )
    except:
        logger.exception( 'event handler failed:' )
        raise

