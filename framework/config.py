#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008-2010 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: config

"""

DBUS_BUS_NAME_PREFIX = "org.freesmartphone"
DBUS_INTERFACE_PREFIX = "org.freesmartphone"
DBUS_PATH_PREFIX = "/org/freesmartphone"

NEEDS_VERSION = 1

__version__ = "1.1.1"

__all__ = ( \
    "DBUS_BUS_NAME_PREFIX",
    "DBUS_INTERFACE_PREFIX",
    "DBUS_PATH_PREFIX",
    "debug",
    "debugto",
    "debugdest",
    "installprefix",
    "rootdir"
)

from configparse import SmartConfigParser
import os
import logging, logging.handlers

loggingmap = { \
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
#
# busmap for subsystems
#
busmap = {}

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
        logging.info( "Using configuration file %s" % p )
        config = SmartConfigParser( p )
        break

if config is None:
    logging.error( "Can't find a configuration file. Looked in %s" % searchpath )
    raise IOError, "can't find configuration file"

version = config.getInt( "frameworkd", "version", 0 )
if version != NEEDS_VERSION:
    logging.warning( "configuration format too old. Please update and add the following lines to your configuration file:" )
    logging.warning( "[frameworkd]" )
    logging.warning( "version = %d" % NEEDS_VERSION )

debug = config.getValue( "frameworkd", "log_level", "INFO" )
debugto = config.getValue( "frameworkd", "log_to", "stderr" )
debugdest = config.getValue( "frameworkd", "log_destination", "/tmp/frameworkd.log" )

# get root logger and yank all existing handlers
rootlogger = logging.getLogger( "" )
rootlogger.setLevel( loggingmap.get( debug, logging.INFO ) )
for handler in rootlogger.handlers:
    rootlogger.removeHandler( handler )

# now that we are clean, setup our actual handler and configure formatter
if debugto == "stderr":
    handler = logging.StreamHandler() # default=stderr
    handler.setFormatter( logging.Formatter( "%(asctime)s.%(msecs)03d %(name)-20s %(levelname)-8s %(message)s", datefmt="%Y.%m.%d %H:%M:%S" ) )
elif debugto == "file":
    handler = logging.FileHandler( debugdest )
    handler.setFormatter( logging.Formatter( "%(asctime)s.%(msecs)03d %(name)-20s %(levelname)-8s %(message)s", datefmt="%Y.%m.%d %H:%M:%S" ) )
elif debugto == "syslog":
    handler = logging.handlers.SysLogHandler( address = "/dev/log" )
    # timestamps are not needed with syslog
    handler.setFormatter( logging.Formatter( "%(name)-8s %(levelname)-8s %(message)s" ) )

# set the handler
rootlogger.addHandler( handler )

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

if installprefix == "/":
    # Installation not found yet, check for symlinked install.
    # e.g. Check if a /usr/... install is a symbolic link to /media/card/...

    separatedFilePath = __file__.split( os.sep )
    for i in range( 2, len( separatedFilePath ) ):
        sepShortFilePath = [ "" ] + separatedFilePath[i:]
        shortFilePath = os.sep.join( sepShortFilePath )
        #logging.debug( "Installprefix check comparing %s, %s" % (shortFilePath, __file__) )

        # Symbolic link check
        if os.path.islink( shortFilePath ) and os.path.samefile( shortFilePath, __file__ ):
            for p in searchpath:     # verify it's an install in the searchpath
                if shortFilePath.startswith(p):
                    installprefix = p
                    break

        # Stop checking if we've found and set the installprefix.
        if installprefix != "/":
            break

logging.info( "Installprefix is %s" % installprefix )

#
# compute root dir
#
# FIXME should rather be named confdir or rulesdir or something like that
possible_rootdirs = os.path.abspath(
    config.getValue( "frameworkd", "rootdir", "../etc/freesmartphone:/etc/freesmartphone:/usr/etc/freesmartphone" )
).split( ':' )
for path in possible_rootdirs:
    if os.path.exists( path ):
        rootdir = path
        break
else:
    logging.warning( "can't find the etc directory; defaulting to /etc/freesmartphone" )
    rootdir = "/etc/freesmartphone"
logging.info( "Etc directory is %s" % rootdir )
