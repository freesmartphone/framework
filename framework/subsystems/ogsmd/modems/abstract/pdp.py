#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

This module is based on pyneod/pypppd.py (C) 2008 M. Dietrich.

Package: ogsmd.modems.abstract
Module: pdp

"""

__version__ = "0.1.1"

from .mediator import AbstractMediator
from .overlay import OverlayFile

import gobject
import os, subprocess, signal, copy

import logging
logger = logging.getLogger( "ogsmd.pdp" )

#=========================================================================#
class Pdp( AbstractMediator ):
#=========================================================================#
    """
    Encapsulates the state of (all) PDP connections on a modem
    """

    def __init__( self, dbus_object, **kwargs ):
        AbstractMediator.__init__( self, dbus_object, None, None, **kwargs )
        self._callchannel = self._object.modem.communicationChannel( "PdpMediator" )

        self.state = "release" # initial state
        self.ppp = None
        self.overlays = []

    #
    # public
    #
    def setParameters( self, apn, user, password ):
        self.pds = copy.copy( self.__class__.PPP_DAEMON_SETUP )
        self.pds[self.__class__.PPP_CONNECT_CHAT_FILENAME] = self.__class__.PPP_DAEMON_SETUP[self.__class__.PPP_CONNECT_CHAT_FILENAME] % apn

        apn, user, password = str(apn), str(user), str(password)

        # merge with modem specific options
        self.ppp_options = self.__class__.PPP_OPTIONS_GENERAL + self._object.modem.dataOptions( "ppp" )

        # merge with user and password settings
        if user:
            logger.info( "configuring ppp for user '%s' w/ password '%s'" % ( user, password ) )
            self.ppp_options += [ "user", user ]
            self.pds[self.__class__.PPP_PAP_SECRETS_FILENAME] = '%s * "%s" *\n' % ( user or '*', password )
            self.pds[self.__class__.PPP_CHAP_SECRETS_FILENAME] =  '%s * "%s" *\n'% ( user or '*', password )

        self.timeout_source = None
        self.childwatch_source = None

        self.default_route = self.route = self._defaultRoute()

    def isActive( self ):
        return self.state == "active"

    def activate( self ):
        self._activate()

    def deactivate( self ):
        self._deactivate()

    def status( self ):
        return self.state

    #
    # private
    #
    def _prepareFiles( self ):
        for filename, overlay in self.pds.iteritems():
            logger.debug( "preparing file %s" % filename )
            f = OverlayFile( filename, overlay=overlay )
            f.store()
            self.overlays.append( f )

    def _recoverFiles( self ):
        for f in self.overlays:
            logger.debug( "recovering file %s" % f.name )
            f.restore()
        self.overlays = []

    def _activate( self ):
        if self.ppp is not None and self.ppp.poll() is None:
            raise Exception( "already active" )

        self.port = str( self._object.modem.dataPort() )
        if not self.port:
            raise Exception( "no device" )

        logger.debug( "activate got port %s" % self.port )
        ppp_commandline = [ self.__class__.PPP_BINARY, self.port ] + self.ppp_options
        logger.info( "launching ppp as commandline %s" % ppp_commandline )

        self._prepareFiles()

        self.ppp = subprocess.Popen( ppp_commandline )

        # FIXME bad polling here
        self.timeout_source = gobject.timeout_add_seconds( 2, self._pollInterface )

        logger.info( "pppd launched, pid %d. See logread -f for output." % self.ppp.pid )

        # FIXME that's premature. we might adopt the following states:
        # "setup", "active", "shutdown", "release"

        self._updateState( "outgoing" )

    def _updateState( self, newstate ):
        if newstate != self.state:
            self.state = newstate
            self._object.ContextStatus( 1, newstate, {} )

    def _deactivate( self ):
        if self.ppp.poll() is not None:
            return

        logger.info( "shutting down pppd, pid %d." % self.ppp.pid )

        os.kill( self.ppp.pid, signal.SIGTERM )
        #os.kill( self.ppp.pid, signal.SIGKILL )

        logger.debug( "waiting for process to quit..." )
        self.ppp.wait()

        self._spawnedProcessDone()

    def _spawnedProcessDone( self ):
        logger.info( "pppd exited with code %d" % self.ppp.returncode )

        # FIXME check whether this was a planned exit or not, if not, try to recover

        self._updateState( "release" )
        self._recoverFiles()

        # FIXME find a better way to restore the default route
        os.system( "ifdown %s" % self.default_route )
        os.system( "ifup %s" % self.default_route )

    def _defaultRoute( self ):
        f = open( "/proc/net/route", 'r' )
        l = f.readlines()
        f.close()
        for n in l:
            n = n.split('\t')
            if n[1] == "00000000":
                return n[0]
        return ""

    def _pollInterface( self ):
        """Gets frequently called from mainloop to check the default route."""
        # FIXME use netlink socket to be notified here!
        route = self._defaultRoute()
        logger.debug( "route status. old=%s, last=%s, current=%s" % ( self.default_route, self.route, route ) )
        if route != self.route:
            self.route = route
            if route == "ppp0":
                self._updateState( "active" )
            else:
                self._updateState( "release" )
        return True

    # class wide constants constants

    PPP_CONNECT_CHAT_FILENAME = "/var/tmp/ogsmd/gprs-connect-chat"
    PPP_DISCONNECT_CHAT_FILENAME = "/var/tmp/ogsmd/gprs-disconnect-chat"

    PPP_PAP_SECRETS_FILENAME = "/etc/ppp/pap-secrets"
    PPP_CHAP_SECRETS_FILENAME = "/etc/ppp/chap-secrets"

    PPP_OPTIONS_GENERAL = [ "connect", PPP_CONNECT_CHAT_FILENAME, "disconnect", PPP_DISCONNECT_CHAT_FILENAME ]

    PPP_BINARY = "/usr/sbin/pppd"

    PPP_DAEMON_SETUP = {}

    PPP_DAEMON_SETUP[ PPP_CONNECT_CHAT_FILENAME ] = r"""#!/bin/sh -e
exec /usr/sbin/chat -v\
    'ABORT' 'BUSY'\
    'ABORT' 'DELAYED'\
    'ABORT' 'ERROR'\
    'ABORT' 'NO ANSWER'\
    'ABORT' 'NO CARRIER'\
    'ABORT' 'NO DIALTONE'\
    'ABORT' 'RINGING'\
    'ABORT' 'VOICE'\
    'TIMEOUT' '5'\
    '' '+++ATZ'\
    'OK-\k\k\k\d+++ATH-OK' 'ATE0'\
    'OK' 'AT+CMEE=2'\
    'OK' 'AT+CPIN?'\
    'READY' '\c'\
    'OK' 'AT+CGDCONT=1,"IP","%s"'\
    'TIMEOUT' '180'\
    'OK' 'ATD*99#'\
    'CONNECT' '\d\c'
"""

    PPP_DAEMON_SETUP[ PPP_DISCONNECT_CHAT_FILENAME ] = r"""#!/bin/sh -e
echo disconnect script running...
"""

    PPP_DAEMON_SETUP["/etc/ppp/ip-up.d/08setupdns"] = """#!/bin/sh -e
cp /var/run/ppp/resolv.conf /etc/resolv.conf
"""

    PPP_DAEMON_SETUP["/etc/ppp/ip-down.d/92removedns"] = """#!/bin/sh -e
echo nameserver 127.0.0.1 > /etc/resolv.conf
"""

    PPP_DAEMON_SETUP[PPP_PAP_SECRETS_FILENAME] = '* * "%s" *\n' % ''

    PPP_DAEMON_SETUP[PPP_CHAP_SECRETS_FILENAME] =  '* * "%s" *\n'% ''

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
