# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   ogsmd-calls Backend Plugin
#
#   http://openmoko.org/
#
#   Copyright (C) 2009 by Thomas "Heinervdm" Zimmermann (zimmermann@vdm-design.de)
#                         Sebastian dos Krzyszkowiak (seba.dos1@gmail.com)
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

#"""pypimd ogsmd-calls Backend Plugin"""
from dbus import SystemBus
import time

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager
from backend_manager import BackendManager, Backend
from helpers import *

import framework.patterns.tasklet as tasklet
from framework.config import config

_DOMAINS = ('Calls', )


#----------------------------------------------------------------------------#
class OgsmdCallsBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'ogsmd-Calls'
    properties = []

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

    def handle_call_status(self, id, call_status, call_props):
        #TODO: handle calls on multiple lines
        if not self.props.has_key('Answered'):
            self.props['Answered']=0
        if call_props.has_key('mode'):
            self.props['Type']='gsm_'+call_props['mode']
        if call_props.has_key('peer'):
            peer = phone_number_to_tel_uri(call_props["peer"])
        elif self.props.has_key('Peer'):
            peer = self.props['Peer']

        if call_status == "incoming":
            try:
                self.props['Peer'] = peer
            except:
                pass
            self.props['Direction'] = 'in'
        elif call_status == "outgoing":
            self.props['Peer'] = peer
            self.props['Direction'] = 'out'
        elif call_status == "active":
            self.props['Answered'] = 1
            self.props['Timestamp'] = time.time()
        elif call_status == "release":
            if self.props.has_key('Timestamp'):   
                self.props['Duration'] = time.time() - self.props['Timestamp']
            else:
                self.props['Timestamp'] = time.time()
            self.props['Timezone'] = time.tzname[time.daylight]
            self.props['New']=1
            if self.props['Direction']=='in' and not self.props['Answered']:
                self._domain_handlers['Calls'].register_missed_call(self, self.props)
            else:
                self._domain_handlers['Calls'].Add(self.props)

            self.props = {}

    @tasklet.tasklet
    def load_entries(self):
        bus = SystemBus()
        if not self.handler:
            bus.add_signal_receiver(self.handle_call_status, signal_name='CallStatus', dbus_interface='org.freesmartphone.GSM.Call', bus_name='org.freesmartphone.ogsmd')
            self.handler = True
