#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: config

"""

DBUS_BUS_NAME_PREFIX = "org.freesmartphone"
DBUS_INTERFACE_PREFIX = "org.freesmartphone"
DBUS_PATH_PREFIX = "/org/freesmartphone"

NEEDS_VERSION = 1

__version__ = "1.0.0"

from configparse import SmartConfigParser

from syslog import LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG

import os

import logging
logger = logging.getLogger( "frameworkd" )


# FIXME This dict map syslog message levels to logging message levels
# FIXME Remove this when we have removed all of the deprecated 'LOG' calls
logging_levels_map = {
    LOG_ERR :       logging.ERROR,
    LOG_WARNING :   logging.WARNING,
    LOG_INFO :      logging.INFO,
    LOG_DEBUG :     logging.DEBUG,
}

def LOG(level, *values):
    """log a message

       this function is deprecated, we should use logging module instead
    """
    if level == LOG_ERR:
        values = values + (format_exc(),)
    logger.log(logging_levels_map[level], ' '.join(str(i) for i in values))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)-8s %(levelname)-8s %(message)s'
)

# init configuration
config = None
for p in [
        os.path.expanduser( "~/.frameworkd.conf" ),
        "/etc/frameworkd.conf",
        os.path.join( os.path.dirname( __file__ ), "../conf/frameworkd.conf" ),
        os.path.expanduser("~/.frameworkd.conf")
    ]:
    if os.path.exists( p ):
        config = SmartConfigParser( p )
        break

if not config:
    logger.error("Can't find a configuration file")
    raise IOError
logger.info( "Using configuration file %s" % config )

version = config.getInt( "frameworkd", "version", 0 )
if version != NEEDS_VERSION:
    logger.warning( "configuration format too old. Please update and add the following lines to your configuration file:" )
    logger.warning( "[frameworkd]" )
    logger.warning( "version = %d" % NEEDS_VERSION )

