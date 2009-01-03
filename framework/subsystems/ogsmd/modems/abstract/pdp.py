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

__version__ = "0.3.0"
MODULE_NAME = "ogsmd.modems.abstract.pdp"

from .mediator import AbstractMediator
from .overlay import OverlayFile

from framework.patterns.kobject import KObjectDispatcher
from framework.patterns.processguard import ProcessGuard

import gobject
import os, subprocess, signal, copy

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class Pdp( AbstractMediator ):
#=========================================================================#
    """
    Encapsulates the state of (all) PDP connections on a modem
    """

    _instance = None

    @classmethod
    def getInstance( klass, dbus_object=None ):
        if klass._instance is None and dbus_object is not None:
            klass._instance = Pdp( dbus_object )
        return klass._instance

    def __init__( self, dbus_object, **kwargs ):
        AbstractMediator.__init__( self, dbus_object, None, None, **kwargs )
        self._callchannel = self._object.modem.communicationChannel( "PdpMediator" )
        self._netchannel = self._object.modem.communicationChannel( "NetworkMediator" )

        self.state = "release" # initial state
        self.ppp = None
        self.overlays = []

        # FIXME: add match only while running pppd
        KObjectDispatcher.addMatch( "addlink", "", self._onAddLinkEvent )

    def _onInterfaceChange( action, path, **kwargs ):
        logger.debug( "detected interface change", action, path )

    #
    # public
    #
    def setParameters( self, apn, user, password ):
        self.pds = copy.copy( self.__class__.PPP_DAEMON_SETUP )
        self.pds[self.__class__.PPP_CONNECT_CHAT_FILENAME] = self.__class__.PPP_DAEMON_SETUP[self.__class__.PPP_CONNECT_CHAT_FILENAME] % apn

        apn, user, password = str(apn), str(user), str(password)

        # merge with modem specific options
        self.ppp_options = self.__class__.PPP_OPTIONS_GENERAL + self._object.modem.data( "pppd-configuration" )

        # merge with user and password settings
        if user:
            logger.info( "configuring ppp for user '%s' w/ password '%s'" % ( user, password ) )
            self.ppp_options += [ "user", user ]
            self.pds[self.__class__.PPP_PAP_SECRETS_FILENAME] = '%s * "%s" *\n' % ( user or '*', password )
            self.pds[self.__class__.PPP_CHAP_SECRETS_FILENAME] =  '%s * "%s" *\n'% ( user or '*', password )

        self.childwatch_source = None

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
        if self.ppp is not None and self.ppp.isRunning():
            raise Exception( "already active" )

        self.port = str( self._object.modem.dataPort() )
        if not self.port:
            raise Exception( "no device" )

        logger.debug( "activate got port %s" % self.port )
        ppp_commandline = [ self.__class__.PPP_BINARY, self.port ] + self.ppp_options
        logger.info( "launching ppp as commandline %s" % ppp_commandline )

        self._prepareFiles()
        self.ppp = ProcessGuard( ppp_commandline )
        self.ppp.execute( onExit=self._spawnedProcessDone, onError=self._onPppError, onOutput=self._onPppOutput )

        logger.info( "pppd launched. See syslog (e.g. logread -f) for output." )

        # FIXME that's somewhat premature. we might adopt the following states:
        # "setup", "active", "shutdown", "release"

        self._updateState( "outgoing" )

    def _updateState( self, newstate ):
        if newstate != self.state:
            self.state = newstate
            self._object.ContextStatus( 1, newstate, {} )

    def _deactivate( self ):
        logger.info( "shutting down pppd" )
        self.ppp.shutdown()

    def _spawnedProcessDone( self, pid, exitcode, exitsignal ):
        logger.info( "pppd exited with code %d, signal %d" % ( exitcode, exitsignal ) )

        # FIXME check whether this was a planned exit or not, if not, try to recover

        self._updateState( "release" )
        self._recoverFiles()

        # FIXME at this point, the default route might be wrong, if someone killed pppd

        # force releasing context and attachment to make sure that
        # the next ppp setup will find the data port in command mode
        self._netchannel.enqueue( "+CGACT=0;+CGATT=0", lambda a,b:None, lambda a,b:None )

    def _onAddLinkEvent( self, action, path, **properties ):
        """
        Called by KObjectDispatcher
        """
        try:
            device = properties["dev"]
            flags = properties["flags"]
        except KeyError:
            pass # not enough information
        else:
            if device == "ppp0" and "UP" in flags:
                self._updateState( "active" )

    def _onPppError( self, text ):
        print "ppp error:", repr(text)

    def _onPppOutput( self, text ):
        print "ppp output:", repr(text)

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
    '' '+++AT'\
    'OK-\k\k\k\d+++ATH-OK' 'ATE0Q0V1'\
    'OK' 'AT+CMEE=2'\
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
