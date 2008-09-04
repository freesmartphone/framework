#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

This module is based on pyneod/pypppd.py (C) 2008 M. Dietrich.

Package: ogsmd.modems.abstract
Module: pdp

"""

__version__ = "0.1.0"

from .mediator import AbstractMediator
from .overlay import OverlayFile

import gobject
import os, signal, copy

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
        self.cpid = -1
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
            self.ppp_options += [ "user", '"%s"' % user ]
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
        if self.cpid >= 0:
            raise Exception( "already active" )

        self.port = str( self._object.modem.dataPort() )
        if not self.port:
            raise Exception( "no device" )

        logger.debug( "activate got port %s" % self.port )
        ppp_arguments = [ self.__class__.PPP_BINARY, self.port ] + self.ppp_options
        logger.info( "launching ppp with commandline %s" % ppp_arguments )

        self._prepareFiles()

        self.cpid, fdin, fdout, fderr = gobject.spawn_async(
            ppp_arguments,
            standard_input = False,
            standard_output = True,
            standard_error = True,
            flags = gobject.SPAWN_DO_NOT_REAP_CHILD )

        # FIXME launch watchdog here -- if the ppp is not getting launched, we have allocated
        # a virtual channel that never gets freed (need to open and close it)

        self.fds = fdin, fdout, fderr

        self.output_sources = [ gobject.io_add_watch( fdout, gobject.IO_IN, self._spawnedProcessOutput ),
                                gobject.io_add_watch( fderr, gobject.IO_IN, self._spawnedProcessOutput ) ]
        self.childwatch_source = gobject.child_watch_add( self.cpid, self._spawnedProcessDone )
        # FIXME bad polling here
        self.timeout_source = gobject.timeout_add_seconds( 2, self._pollInterface )

        logger.info( "pppd launched, pid %d. See logread -f for output." % self.cpid )

        # FIXME that's premature. we might adopt the following states:
        # "setup", "active", "shutdown", "release"

        self._updateState( "outgoing" )

    def _updateState( self, newstate ):
        if newstate != self.state:
            self.state = newstate
            self._object.ContextStatus( 1, newstate, {} )

    def _deactivate( self ):
        if self.cpid < 0:
            raise Exception('already inactive')

        logger.info( "shutting down pppd, pid %d." % self.cpid )

        os.kill( self.cpid, signal.SIGINT )

        # control flow will continue in self._spawnedProcessDone
        #p, r = waitpid(self.cpid, 0)

    def _spawnedProcessOutput( self, source, condition ):
        """Gets called when ppp outputs anything."""
        data = os.read( source, 512 )
        logger.debug( "got output from ppp: %s" % repr(data) )
        return True

    def _spawnedProcessDone( self, pid, condition ):
        """Gets called from mainloop when ppp exits."""

        # FIXME find a way to distinguish between a planned shutdown
        # (our kill) and an unexpected shutdown
        #
        # Exit codes:
        # 8 - connect script failed
        # 5 - normal abort due to SIGINT
        #

        for source in [ self.childwatch_source, self.timeout_source ] + self.output_sources:
            if source is not None:
                gobject.source_remove( source )
        for fd in self.fds:
            if fd is not None:
                os.close( fd )

        exitcode = (condition >> 8) & 0xFF
        exitsignal = condition & 0xFF
        logger.info( "pppd exited with code %d and signal %d" % ( exitcode, exitsignal ) )

        # FIXME check whether this was a planned exit or not, if not, try to recover

        self._updateState( "release" )

        self.cpid = -1
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
exec /usr/sbin/chat -v\
    'ABORT' 'OK'\
    'ABORT' 'BUSY'\
    'ABORT' 'DELAYED'\
    'ABORT' 'NO ANSWER'\
    'ABORT' 'NO CARRIER'\
    'ABORT' 'NO DIALTONE'\
    'ABORT' 'VOICE'\
    'ABORT' 'ERROR'\
    'ABORT' 'RINGING'\
    'TIMEOUT' '60'\
    '' '\k\k\k\d+++ATH'\
    'NO CARRIER-AT-OK' ''
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
