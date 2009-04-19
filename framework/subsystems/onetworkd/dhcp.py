#!/usr/bin/env python
"""
Network

(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: onetworkd
Module: dhcp

Support for the Dynamic Host Configuration Protocol
"""

MODULE_NAME = "onetworkd"
__version__ = "0.0.1"

from framework.patterns.utilities import killall

from helpers import readFromFile, writeToFile

import subprocess

import logging
logger = logging.getLogger( MODULE_NAME )

ETC_RESOLV_CONF = "/etc/resolv.conf"
ETC_UDHCPD_CONF = "/etc/udhcpd.conf"

#============================================================================#
def launchDaemon():
#============================================================================#
    killall( "udhcpd" )
    subprocess.call( "udhcpd" )

#============================================================================#
def prepareDaemonConfigurationForInterface( iface ):
#============================================================================#
    name = iface.name()
    address = iface.ipAddress4()

    nameservers = ""
    resolv_conf = readFromFile( ETC_RESOLV_CONF ).split( '\n' )
    for line in resolv_conf:
        if line.startswith( "nameserver" ):
            nameserver = line.strip().split( ' ' )[1]
            nameservers += nameserver
            nameservers += " "

    conf_file = daemon_conf_file_template % ( name, nameservers, address )

    writeToFile( ETC_UDHCPD_CONF, conf_file )

#============================================================================#
daemon_conf_file_template = """# freesmartphone.org /etc/udhcpd.conf
start           192.168.0.20  # lease range
end             192.168.0.199 # lease range
interface       %s            # listen on interface
option dns      %s            # grab from resolv.conf
option  subnet  255.255.255.0
opt     router  %s            # address of interface
option  lease   864000        # 10 days of seconds
"""
#============================================================================#
