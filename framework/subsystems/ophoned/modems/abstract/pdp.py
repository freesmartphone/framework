#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

This module is based on pyneod/pypppd.py (C) 2008 M. Dietrich.

Package: ophoned.modems.abstract
Module: pdp

"""

from ophoned.gsm.decor import logged
from .mediator import AbstractMediator
from .overlay import OverlayFile
from framework.config import LOG, LOG_INFO, LOG_ERR, LOG_DEBUG
import gobject
import os

#=========================================================================#
class Pdp( AbstractMediator ):
#=========================================================================#
    """
    Encapsulates the state of (all) PDP connections on a modem
    """

    def __init__( self, dbus_object, **kwargs ):
        AbstractMediator.__init__( self, dbus_object, None, None, **kwargs )
        self._callchannel = self._object.modem.communicationChannel( "PdpMediator" )

        self.active = False
        self.apn = ""
        self.user = ""
        self.password = ""

        self.cpid = -1
        self.last_status = {}
        self.overlays = []

        self.shutdown = False

    #
    # public
    #
    def setParameters( self, apn, user, password ):
        self.apn = apn
        self.user = user
        self.password = password

        self.ppp_options = ppp_options + self._object.modem.dataOptions( "ppp" )

        self.timeout_source = None
        self.childwatch_source = None

    def isActive( self ):
        return self.active

    @logged
    def activate( self ):
        self._activate()

    def deactivate( self ):
        self._deactivate()

    #
    # private
    #
    def _spawnedProcessDone( self, pid, condition ):
        """Gets called from mainloop when ppp exits."""

        # FIXME find a way to distinguish between a planned shutdown
        # (our kill) and an unexpected shutdown

        self.active = False

        if self.childwatch_source is not None:
            gobject.source_remove( self.childwatch_source )
        if self.timeout_source is not None:
            gobject.source_remove( self.timeout_source )

        exitcode = (condition >> 8) & 0xFF
        exitsignal = condition & 0xFF
        LOG( LOG_DEBUG, __name__, "ppp exited with code", exitcode, "and signal", exitsignal )

        if os.path.exists( self.port ):
            try:
                open( self.port, "rw" ).close()
            except IOError:
                pass

        self.cpid = -1
        self._recoverFiles()

        # FIXME find a better way to restore the default route
        os.system( "ifdown usb0" )
        os.system( "ifup usb0" )

    @logged
    def _prepareFiles( self ):
        for filename, overlay in ppp_daemon_setup.iteritems():
            LOG( LOG_DEBUG, __name__, "preparing file", filename )
            f = OverlayFile( filename, overlay=overlay )
            f.store()
            self.overlays.append( f )

    @logged
    def _recoverFiles( self ):
        for f in self.overlays:
            LOG( LOG_DEBUG, __name__, "recovering file", f.name )
            f.restore()
        self.overlays = []

    @logged
    def _activate( self ):
        if self.cpid >= 0:
            raise Exception( "already active" )

        self.port = str( self._object.modem.dataPort() )
        if not self.port:
            raise Exception( "no device" )

        LOG( LOG_INFO, __name__, 'activate got port', self.port )
        ppp_arguments = [ ppp_binary, self.port ] + self.ppp_options
        LOG( LOG_INFO, __name__, "launching ppp commandline", ppp_arguments )

        self._prepareFiles()

        self.cpid, _, _, _ = gobject.spawn_async(
                ppp_arguments,
                standard_input = False,
                standard_output = False,
                standard_error = False,
                flags = gobject.SPAWN_DO_NOT_REAP_CHILD,
            )
        LOG( LOG_INFO, __name__, "ppp launched w/pid", self.cpid )
        self.childwatch_source = gobject.child_watch_add( self.cpid, self._spawnedProcessDone )
        self.timeout_source = gobject.timeout_add_seconds( 12, self._cbPollInterface )

        # FIXME that's premature. we might adopt the following states:
        # "setup", "active", "shutdown", "release"
        self.active = True

    def _deactivate( self ):
        if self.cpid < 0:
            raise Exception('already inactive')

        LOG( LOG_INFO, __name__, 'shutting down pppd w/pid', self.cpid )

        os.kill( self.cpid, SIGINT )

        # control flow will continue in self._spawnedProcessDone

        #LOG(LOG_INFO, __name__, 'Activate waiting for pppd')
        #p, r = waitpid(self.cpid, 0)
        #LOG(LOG_INFO, __name__, 'Activate pppd returned', r)

    def get_default_route( self ):
        f = open('/proc/net/route', 'r')
        l = f.readlines()
        f.close()
        for n in l:
            n = n.split('\t')
            if n[1] == '00000000':
                return n[0]
        return ''

    def _cbPollInterface( self ):
        status = dict(device=self.get_default_route())
        LOG(LOG_DEBUG, __name__, '__poll', status, self.last_status)
        #if self.last_status != status:
        #    self.Status(status)
        return True

#=========================================================================#
# some globals for now
#=========================================================================#
GPRS_APN = "internet.eplus.de"
GPRS_USER = ""
GPRS_PASSWORD = ""

ppp_options = [ "connect", "/var/tmp/ophoned/gprs-connect-chat",
                "disconnect", "/var/tmp/ophoned/gprs-disconnect-chat" ]

ppp_binary = "/usr/sbin/pppd"

ppp_daemon_setup = {}

ppp_daemon_setup["/var/tmp/ophoned/gprs-connect-chat"] = r"""#!/bin/sh -e
exec /usr/sbin/chat -v\
    'ABORT' 'BUSY'\
    'ABORT' 'DELAYED'\
    'ABORT' 'ERROR'\
    'ABORT' 'NO ANSWER'\
    'ABORT' 'NO CARRIER'\
    'ABORT' 'NO DIALTONE'\
    'ABORT' 'RINGING'\
    'ABORT' 'VOICE'\
    'TIMEOUT' '3'\
    '' 'ATZ'\
    'OK-\k\k\k\d+++ATH-OK' 'ATE0'\
    'OK' 'AT+CMEE=2'\
    'OK' 'AT+CPIN?'\
    'READY' '\c'\
    'OK' 'AT+CGDCONT=1,"IP","%s"'\
    'TIMEOUT' '180'\
    'OK' 'ATD*99#'\
    'CONNECT' '\d\c'
"""% GPRS_APN

ppp_daemon_setup["/var/tmp/ophoned/gprs-disconnect-chat"] = r"""#!/bin/sh -e
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

ppp_daemon_setup["/etc/ppp/chap-secrets"] = '* * "%s" *\n' % ''

ppp_daemon_setup["/etc/ppp/pap-secrets"] =  '* * "%s" *\n'% ''

ppp_daemon_setup["/etc/ppp/ip-up.d/08setupdns"] = """#!/bin/sh -e
cp /var/run/ppp/resolv.conf /etc/resolv.conf
"""

ppp_daemon_setup["/etc/ppp/ip-down.d/92removedns"] = """#!/bin/sh -e
echo nameserver 127.0.0.1 > /etc/resolv.conf
"""

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    import dbus
    bus = dbus.SystemBus()
    handler = GprsHandler( bus )
    openlog( "gprshandler", LOG_PERROR, LOG_DAEMON )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
