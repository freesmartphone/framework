#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned.modems.abstract
Module: pdp

TODO:
    * ppp configuration data is modem specific => refactor into modem class

"""

from .mediator import AbstractMediator

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

    def setParameters( self, apn, user, password ):
        self.apn = apn
        self.user = user
        self.password = password

    def isActive( self ):
        return self.active

    def activate( self ):
        self.handler = GprsHandler()
        self.handler.activate( True )

    def deactivate( self ):
        self.handler.activate( False )

GPRS_APN = "internet.eplus.de"

from time import time
from os import system, kill, chmod
from os.path import exists
from stat import S_IRWXU, S_IRWXG, S_IRWXO
from signal import SIGINT, signal
from time import sleep
from framework.config import LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG
from gobject import timeout_add, child_watch_add, spawn_async
from syslog import openlog, LOG_PERROR, LOG_DAEMON
import dbus

# GprsHandler
# copyright: m. dietrich

#=========================================================================#
class GprsHandler( object ):
#=========================================================================#
    __init_filename = '/var/tmp/gprs-connect-chat'
    __hangup_filename = '/var/tmp/gprs-disconnect-chat'
    __patch_files = {
        __init_filename: r"""#!/bin/sh -e
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
"""% GPRS_APN,
        '/etc/ppp/chap-secrets': '* * "%s" *\n'% '',
        '/etc/ppp/pap-secrets': '* * "%s" *\n'% '',
        '/etc/ppp/ip-up.d/08setupdns': """#!/bin/sh -e
cp /var/run/ppp/resolv.conf /etc/resolv.conf
""",
        '/etc/ppp/ip-down.d/92removedns': """#!/bin/sh -e
echo nameserver 127.0.0.1 > /etc/resolv.conf
""",
        __hangup_filename: r"""#!/bin/sh -e
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
""",
    }
    __pppd_command = '/usr/sbin/pppd'
    __pppd_options = [
        '115200',
        'nodetach',
        'connect', __init_filename,
        'crtscts',
        'defaultroute',
        'debug',
        'disconnect', __hangup_filename,
        'hide-password',
        'holdoff', '3',
        'ipcp-accept-local',
        'ktune',
        'lcp-echo-failure', '8',
        'lcp-echo-interval', '3',
        'ipcp-max-configure', '32',
        'lock',
        'noauth',
        #'demand',
        'noipdefault',
        'novj',
        'novjccomp',
        #'persist',
        'proxyarp',
        'replacedefaultroute',
        'usepeerdns',
        ]

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.cpid = -1
        self.port = ''
        self.last_status = dict(device='')
        timeout_add(12 * 1000, self.__poll)

    def __child_watch(self, pid, condition, user_data):
        print '__child_watch', pid, condition, user_data

    def _requestChannelPath( self ):
        """Allocate a new channel from the MUXer."""
        oMuxer = self.bus.get_object( "org.pyneo.muxer", "/org/pyneo/Muxer" )
        self.iMuxer = dbus.Interface( oMuxer, "org.freesmartphone.GSM.MUX" )
        return self.iMuxer.AllocChannel( "ophoned.ppp" )
        del self.iMuxer

    def activate(self, on):
        LOG(LOG_DEBUG, __name__, 'Activate')
        try:
            if on:
                if self.cpid >= 0:
                    raise Exception('already active')
                self.port = str( self._requestChannelPath() )
                if not self.port:
                    raise Exception('no device')
                # go direct self.port = '/dev/ttySAC0'
                LOG(LOG_INFO, __name__, 'Activate got port', self.port)
                for filename, content in self.__patch_files.items():
                    LOG(LOG_DEBUG, __name__, 'change file for our needs:', filename);
                    f = open(filename, 'w')
                    f.write(content)
                    f.close()
                    chmod(filename, S_IRWXU|S_IRWXO|S_IRWXO)
                self.cpid, _, _, _ = spawn_async(
                    [self.__pppd_command, self.port, ] + self.__pppd_options,
                    standard_input=False, standard_output=False, standard_error=False,
                    #dict(PATH='/bin:/usr/bin:/sbin:/usr/sbin', ),
                    )
                child_watch_add(self.cpid, self.__child_watch)
            else:
                if self.cpid < 0: raise Exception('already inactive')
                try:
                    LOG(LOG_INFO, __name__, 'Activate kill pppd pid', self.cpid)
                    kill(self.cpid, SIGINT)
                    #LOG(LOG_INFO, __name__, 'Activate waiting for pppd')
                    #p, r = waitpid(self.cpid, 0)
                    #LOG(LOG_INFO, __name__, 'Activate pppd returned', r)
                    if exists(self.port):
                        try: open(self.port, 'rw').close()
                        except: pass
                finally:
                    self.cpid = -1
                system('ifdown usb0')
                system('ifup usb0')
        except Exception, e:
            LOG(LOG_ERR, __name__, 'Activate', e)

    def Status(self, newmap):
        self.last_status = newmap
        LOG(LOG_INFO, __name__, 'Status', self.last_status)

    def GetStatus(self):
        return self.last_status
        LOG(LOG_INFO, __name__, 'GetStatus', self.last_status)

    def get_default_route(self):
        f = open('/proc/net/route', 'r')
        l = f.readlines()
        f.close()
        for n in l:
            n = n.split('\t')
            if n[1] == '00000000':
                return n[0]
        return ''

    def __poll(self):
        status = dict(device=self.get_default_route())
        LOG(LOG_DEBUG, __name__, '__poll', status, self.last_status)
        if self.last_status != status:
            self.Status(status)
        return True

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
