# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   ogsmd-calls Backend Plugin
#
#   http://openmoko.org/
#
#   Copyright (C) 2009 by Sebastian dos Krzyszkowiak (seba.dos1@gmail.com)
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

"""opimd ogsmd-calls Backend Plugin"""
from dbus import SystemBus
import time

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager
from backend_manager import PIMB_IS_HANDLER
from backend_manager import BackendManager, Backend
from helpers import *

import framework.patterns.tasklet as tasklet
from framework.config import config

_DOMAINS = ('Calls', )


#----------------------------------------------------------------------------#
class OgsmdCallsBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'ogsmd-Calls'
    properties = [PIMB_IS_HANDLER]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(OgsmdCallsBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []

        self.props = {}
        self.handler = False

        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)


    def __repr__(self):
        return self.name


#    def __del__(self):


    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        return _DOMAINS

    def handle_call_status(self, line, call_status, call_props):

        if not self.props.has_key(line):
            self.props[line] = {}
            self.props[line]['Line'] = str(line)

        if not self.props[line].has_key('Answered'):
            self.props[line]['Answered']=0
        if call_props.has_key('mode'):
            self.props[line]['Type']='gsm_'+call_props['mode']
        if call_props.has_key('peer'):
            peer = phone_number_to_tel_uri(call_props["peer"])
        elif self.props[line].has_key('Peer'):
            peer = self.props[line]['Peer']

        if call_status == "incoming":
            try:
                self.props[line]['Peer'] = peer
            except:
                pass
            self.props[line]['Direction'] = 'in'
        elif call_status == "outgoing":
            self.props[line]['Peer'] = peer
            self.props[line]['Direction'] = 'out'
        elif call_status == "active":
            self.props[line]['Answered'] = 1
            self.props[line]['Timestamp'] = int(time.time())
        elif call_status == "release":
            if self.props[line].has_key('Timestamp'):
                self.props[line]['Duration'] = int(time.time() - self.props[line]['Timestamp'])
            else:
                self.props[line]['Timestamp'] = int(time.time())
            self.props[line]['Timezone'] = time.tzname[time.daylight]
            self.props[line]['New']=1
            if self.props[line]['Direction']=='in' and not self.props[line]['Answered']:
                self._domain_handlers['Calls'].register_missed_call(self, self.props[line])
            else:
                self._domain_handlers['Calls'].Add(self.props[line])

            del self.props[line]

    def disable(self):
        if self.handler:
            self.signal.remove()
            self.handler = False

    @tasklet.tasklet
    def load_entries(self):
        bus = SystemBus()
        if not self.handler:
            self.signal = bus.add_signal_receiver(self.handle_call_status, signal_name='CallStatus', dbus_interface='org.freesmartphone.GSM.Call', bus_name='org.freesmartphone.ogsmd')
            self.handler = True
        self._initialized = True
        yield True
