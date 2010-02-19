#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2009 by Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Type manager
"""

DBUS_BUS_NAME_FSO = "org.freesmartphone.opimd"
DBUS_PATH_BASE_FSO = "/org/freesmartphone/PIM"
DIN_BASE_FSO = "org.freesmartphone.PIM"

from domain_manager import DomainManager
from helpers import *

from framework.config import config, busmap

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import re
import logging
logger = logging.getLogger('opimd')

#----------------------------------------------------------------------------#

_DBUS_PATH_TYPES = DBUS_PATH_BASE_FSO + '/Types'
_DIN_TYPES = DIN_BASE_FSO + '.Types'

#Consist of type and python type (latter is for internal use)
#Allowed: int, str, unicode, float (and long?).
# unicode should be used for all user related strings that may have unicode
# in, even phonenumber
_TYPES = {
                'objectpath':   str,
                'phonenumber':  unicode,
                'number':       float,
                'integer':      int,
                'address':      unicode,
                'email':        unicode,
                'name':         unicode,
                'date':         int,
                'uri':          unicode,
                'photo':        unicode,
                'text':         unicode,
                'longtext':     unicode,
                'boolean':      int,
                'timezone':     unicode,
                'entryid':      int,
                'generic':      unicode
         }

#----------------------------------------------------------------------------#
class TypeManager(DBusFBObject):
#----------------------------------------------------------------------------#

    Types = _TYPES

    def __init__(self):
        """Initializes the type manager"""

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_TYPES )

        # Still necessary?
        self.interface = _DIN_TYPES
        self.path = _DBUS_PATH_TYPES

    @dbus_method(_DIN_TYPES, "", "as")
    def List(self):
        return Types
