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

