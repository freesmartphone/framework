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

__version__ = "1.0.1"

from configparse import SmartConfigParser

import os

import logging
logger = logging.getLogger( "frameworkd" )

loggingmap = { \
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
#
# init configuration
#
config = None
searchpath = [
        os.path.expanduser( "~/.frameworkd.conf" ),
        "/etc/frameworkd.conf",
        os.path.join( os.path.dirname( __file__ ), "../conf/frameworkd.conf" ),
        os.path.expanduser("~/.frameworkd.conf")
    ]
for p in searchpath:
    if os.path.exists( p ):
        logger.info( "Using configuration file %s" % p )
        config = SmartConfigParser( p )
        break

if config is None:
    logger.error( "Can't find a configuration file. Looked in %s" % searchpath )
    raise IOError, "can't find configuration file"

version = config.getInt( "frameworkd", "version", 0 )
if version != NEEDS_VERSION:
    logger.warning( "configuration format too old. Please update and add the following lines to your configuration file:" )
    logger.warning( "[frameworkd]" )
    logger.warning( "version = %d" % NEEDS_VERSION )

debug = config.getValue( "frameworkd", "log_level", "INFO" )
logging.basicConfig( level=loggingmap.get( debug, logging.INFO ), format="%(name)-8s %(levelname)-8s %(message)s" )

#
# compute install prefix
#
installprefix = "/" # unknown first
searchpath = "/usr/local /usr /local/pkg/fso /opt".split()
thisdirname = os.path.dirname( __file__ )
for p in searchpath:
    if thisdirname.startswith( p ):
        installprefix = p
        break

logger.info( "Installprefix is %s" % installprefix )

# remove unused attributes, leaving 'config' and 'debug'
del SmartConfigParser, os, logging, logger
