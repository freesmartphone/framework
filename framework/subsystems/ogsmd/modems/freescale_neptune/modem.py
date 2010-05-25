#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later

Package: ogsmd.modems.freescale_neptune
Module: modem

Freescale Neptune modem class
"""

__version__ = "0.3.1"
MODULE_NAME = "ogsmd.modems.freescale_neptune"

EZXD_PROCESS_NAME = "ezxd"

import mediator

from framework.patterns.utilities import killall

from ogsmd.modems.abstract.modem import AbstractModem

from .channel import CallAndNetworkChannel, MiscChannel, SmsChannel, SimChannel
from .unsolicited import UnsolicitedResponseDelegate

from ogsmd.gsm.decor import logged
from ogsmd.gsm.channel import AtCommandChannel

import logging
logger = logging.getLogger( MODULE_NAME )

import types

import os
import sys
import errno
import fcntl
import termios
import array
import time
import subprocess

muxfds = []
initDone = False

#=========================================================================#
class FreescaleNeptune( AbstractModem ):
#=========================================================================#
    """
    Support for the Freescale Neptune embedded modem as found in the Motorola EZX
    Linux Smartphones E680, A780, A910, A1200, A1600, ROKR E2, ROKR E6, and more.

    We have a hardwired multiplexing mode configuration as follows:
    ----------------------------------------------------------------
       DLC     Description          Cmd     Device      Mode
    ----------------------------------------------------------------
        0   Control Channel         -          -
        1   Voice Call & Network    MM      /dev/mux0   Modem
        2   SMS                     MO      /dev/mux1   Phonebook
        3   SMS                     MT      /dev/mux2   Phonebook
        4   Phonebook               SIM     /dev/mux3   Phonebook
        5   Misc                            /dev/mux4   Phonebook
        6   CSD / Fax             /dev/mux5 /dev/mux8   Modem
        7   GPRS 1                /dev/mux6 /dev/mux9   Modem
        8   GPRS 2                /dev/mux7 /dev/mux10  Modem
        9   Logger CMD            /dev/mux11
        10  Logger Data           /dev/mux12
        11  Test CMD              /dev/mux13
        12  AGPS                  /dev/mux14
        13  NetMonitor            /dev/mux15
    ----------------------------------------------------------------

    ...
    """

    @logged
    def __new__( cls, *args, **kwargs ):
        global initDone
        if not initDone:
            ret = cls._freescale_neptune_modemOn()
            if ret == False:
                return None
            initDone = True

        return AbstractModem.__new__( cls, *args, **kwargs )

    @logged
    def __init__( self, *args, **kwargs ):
        AbstractModem.__init__( self, *args, **kwargs )

        # /dev/mux0
        self._channels[ "CallAndNetwork" ] = CallAndNetworkChannel( self.pathfactory, "/dev/mux1", modem=self )
        # /dev/mux2
        self._channels[ "Sms" ] = SmsChannel( self.pathfactory, "/dev/mux3", modem=self )
        # /dev/mux4
        self._channels[ "Sim" ] = SimChannel( self.pathfactory, "/dev/mux4", modem=self )
        # /dev/mux6
        self._channels[ "Misc" ] = MiscChannel( self.pathfactory, "/dev/mux5", modem=self )

        # configure channels
        self._channels["CallAndNetwork"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )
        self._channels["Sms"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )
        self._channels["Sim"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )
        self._channels["Misc"].setDelegate( UnsolicitedResponseDelegate( self._object, mediator ) )

    def numberToPhonebookTuple( self, nstring ):
        """
        Modem violating GSM 07.07 here. It always includes the '+' for international numbers,
        although this should only be encoded via ntype = '145'.
        """
        if type( nstring ) != types.StringType():
            # even though we set +CSCS="UCS2" (modem charset), the name is always encoded in text format, not PDU.
            nstring = nstring.encode( "iso-8859-1" )

        if nstring[0] == '+':
            return nstring, 145
        else:
            return nstring, 129

    def channel( self, category ):
        if category == "CallMediator" or category == "DeviceMediator" :
            return self._channels["CallAndNetwork"]
        elif category == "UnsolicitedMediator":
            return self._channels["Sms"]
        elif category == "SimMediator":
            return self._channels["Sim"]
        else:
            return self._channels["Misc"]

    def pathfactory(self, name):
        return name

    @staticmethod
    def _freescale_neptune_modemOn():
        global muxfds
        logger.debug("********************** Modem init **********************")
        subprocess.check_call(['modprobe', 'ohci-hcd'])
        time.sleep(2)
        subprocess.check_call(['modprobe', 'moto-usb-ipc'])
        subprocess.check_call(['modprobe', 'ts27010mux'])

        N_TS2710 = 19
        dlci_lines = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        devpath  = "/dev/ttyIPC0"
        counter = 10

        # Loop when opening /dev/ttyIPC0 to have some tolerance
        ipc = None
        while True:
            logger.debug("Trying to open %s... (%d)" % (devpath, counter))
            counter -= 1
            try:
                ipc = os.open(devpath, os.O_RDWR)
            except OSError as e:
                if e.errno == errno.ENODEV and counter > 0:
                    time.sleep(2)
                    continue

            if ipc or counter == 0:
                break

        if not ipc:
            logger.error("Error opening %s" % devpath)
            return False

        logger.debug("Setting ldisc")
        line = array.array('i', [N_TS2710])
        ret = fcntl.ioctl(ipc, termios.TIOCSETD, line, 1)
        if ret != 0:
            logger.error("ioctl error %s" % devpath)
            return False

        for dlci in dlci_lines:
            devpath = "/dev/mux%d" % dlci
            try:
                fd = os.open(devpath, os.O_RDWR | os.O_NOCTTY)
            except OSError as e:
                logger.error("%s: %s" % (devpath, e.strerror))
                #return False

            logger.debug("Opened %s" % devpath)
            muxfds.append(fd)
        return True
